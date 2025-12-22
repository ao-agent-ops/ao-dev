"""
AST transformation for taint tracking.

Rewrites Python code to track data flow through operations:

1. String formatting: f-strings, .format(), % -> taint-aware string functions
2. Function calls: All functions and methods -> exec_func (except dunder methods)
3. Operations: +, -, *, [], +=, etc. -> exec_func with operator functions
4. File operations: open() -> taint_open with persistence

exec_func handles user code directly and third-party code with taint propagation.
"""

import ast
from ao.common.utils import get_ao_py_files


class TaintPropagationTransformer(ast.NodeTransformer):
    """
    AST transformer that wraps operations with taint-aware functions.

    Transforms:
    - String formatting -> taint_fstring_join, taint_format_string, taint_percent_format
    - Function calls -> exec_func (except dunder methods)
    - Operations (+, -, *, [], +=, etc.) -> exec_func with operator functions
    - open() -> taint_open
    """

    def __init__(self, module_to_file=None, current_file=None):
        """
        Initialize the transformer.

        Args:
            module_to_file: Dict mapping user module names to their file paths.
                           Used to identify which modules are user-defined.
            current_file: The path to the current file being transformed.
        """
        self.module_to_file = module_to_file or {}
        self.user_py_files = [*self.module_to_file.values()]
        # also include all files in ao
        self.user_py_files.extend(get_ao_py_files())
        self.current_file = current_file
        self.needs_taint_imports = False  # Track if we need to inject imports
        # Extract the root directory from current_file if available
        if current_file:
            # Find the common prefix between current_file and all module files
            # to determine project_root
            self.project_root = self._extract_project_root(current_file)
        else:
            self.project_root = None

    def _create_exec_func_call(self, op_func_name, args_list, node):
        """Create exec_func call for any operation."""
        self.needs_taint_imports = True

        # Create operator function reference
        op_func = ast.Attribute(
            value=ast.Name(id="operator", ctx=ast.Load()), attr=op_func_name, ctx=ast.Load()
        )

        # Create args tuple and empty kwargs
        args_tuple = ast.Tuple(elts=args_list, ctx=ast.Load())
        kwargs_dict = ast.Dict(keys=[], values=[])

        # Create exec_func call
        new_node = ast.Call(
            func=ast.Name(id="exec_func", ctx=ast.Load()),
            args=[op_func, args_tuple, kwargs_dict],
            keywords=[],
        )

        return ast.copy_location(new_node, node)

    def _create_exec_func_call_custom(self, op_func, args_list, node):
        """Create exec_func call with custom operator function (not from operator module)."""
        self.needs_taint_imports = True

        args_tuple = ast.Tuple(elts=args_list, ctx=ast.Load())
        kwargs_dict = ast.Dict(keys=[], values=[])

        new_node = ast.Call(
            func=ast.Name(id="exec_func", ctx=ast.Load()),
            args=[op_func, args_tuple, kwargs_dict],
            keywords=[],
        )

        return ast.copy_location(new_node, node)

    def _create_augassign_exec_func_call(self, op_func_name, target, value, node):
        """Create assignment with exec_inplace_binop call for augmented assignment operations."""
        self.needs_taint_imports = True

        # Create a copy of target with Load context for use in args
        import copy

        target_load = copy.deepcopy(target)
        if hasattr(target_load, "ctx"):
            target_load.ctx = ast.Load()
        # Recursively fix context for nested attributes/subscripts
        for child in ast.walk(target_load):
            if hasattr(child, "ctx") and not isinstance(child.ctx, ast.Load):
                child.ctx = ast.Load()

        # Use exec_inplace_binop(obj, value, op_name) for in-place operations
        # This preserves TAINT_DICT entries for TaintWrapper objects
        exec_call = ast.Call(
            func=ast.Name(id="exec_inplace_binop", ctx=ast.Load()),
            args=[target_load, value, ast.Constant(value=op_func_name)],
            keywords=[],
        )

        # Transform into assignment: target = exec_inplace_binop(...)
        new_node = ast.Assign(targets=[target], value=exec_call)

        return ast.copy_location(new_node, node)

    def _create_subscript_exec_func_expr(self, op_func_name, target, value, node):
        """Create Expr with exec_setitem/exec_delitem call for subscript operations."""
        self.needs_taint_imports = True

        # Create copies with Load context
        import copy

        target_value_load = copy.deepcopy(target.value)
        target_slice_load = copy.deepcopy(target.slice)

        # Fix context for all nodes in the copies
        for child in ast.walk(target_value_load):
            if hasattr(child, "ctx"):
                child.ctx = ast.Load()
        for child in ast.walk(target_slice_load):
            if hasattr(child, "ctx"):
                child.ctx = ast.Load()

        # Use specialized exec_setitem/exec_delitem instead of exec_func(operator.xxx)
        if op_func_name == "setitem":
            # exec_setitem(obj, key, value)
            call_node = ast.Call(
                func=ast.Name(id="exec_setitem", ctx=ast.Load()),
                args=[target_value_load, target_slice_load, value],
                keywords=[],
            )
        elif op_func_name == "delitem":
            # exec_delitem(obj, key)
            call_node = ast.Call(
                func=ast.Name(id="exec_delitem", ctx=ast.Load()),
                args=[target_value_load, target_slice_load],
                keywords=[],
            )
        else:
            # Fallback to exec_func for other operations
            args_list = [target_value_load, target_slice_load]
            if value is not None:
                args_list.append(value)
            call_node = self._create_exec_func_call(op_func_name, args_list, node)

        new_node = ast.Expr(value=call_node)
        return ast.copy_location(new_node, node)

    def visit_JoinedStr(self, node):
        """Transform f-string literals into taint_fstring_join calls."""
        self.needs_taint_imports = True

        args = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                args.append(value)
            elif isinstance(value, ast.FormattedValue):
                transformed_value = self.visit(value.value)
                args.append(transformed_value)
            else:
                transformed_value = self.visit(value)
                args.append(transformed_value)

        new_node = ast.Call(
            func=ast.Name(id="taint_fstring_join", ctx=ast.Load()),
            args=args,
            keywords=[],
        )
        return ast.copy_location(new_node, node)

    def visit_Call(self, node):
        """Transform function calls to exec_func, taint_format_string, or taint_open."""
        # CRITICAL: Check for method calls BEFORE generic_visit() to prevent
        # visit_Attribute from transforming obj.method into get_attr()

        # Handle method calls: obj.method(args)
        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

            # Skip dunders that could cause issues if wrapped
            # (object construction, attribute access that could recurse)
            skip_dunders = {"__init__", "__new__", "__getattr__", "__setattr__"}
            if func_name in skip_dunders:
                return self.generic_visit(node)

            # Transform .format() calls specially
            if func_name == "format":
                self.needs_taint_imports = True
                # Visit args/kwargs but NOT the object.format attribute
                visited_args = [self.visit(arg) for arg in node.args]
                visited_keywords = [
                    ast.keyword(arg=kw.arg, value=self.visit(kw.value)) for kw in node.keywords
                ]
                visited_obj = self.visit(node.func.value)
                new_node = ast.Call(
                    func=ast.Name(id="taint_format_string", ctx=ast.Load()),
                    args=[visited_obj] + visited_args,
                    keywords=visited_keywords,
                )
                return ast.copy_location(new_node, node)

            # Method call: obj.method(args) -> exec_func(obj, args, kwargs, method_name="method")
            self.needs_taint_imports = True

            # Visit children: args/kwargs and the parent object, but NOT the method attribute
            visited_args = [self.visit(arg) for arg in node.args]
            visited_keywords = [
                ast.keyword(arg=kw.arg, value=self.visit(kw.value)) for kw in node.keywords
            ]
            visited_obj = self.visit(node.func.value)

            args_tuple = ast.Tuple(elts=visited_args, ctx=ast.Load())
            kwargs_dict = ast.Dict(
                keys=[ast.Constant(value=kw.arg) if kw.arg else None for kw in visited_keywords],
                values=[kw.value for kw in visited_keywords],
            )

            new_node = ast.Call(
                func=ast.Name(id="exec_func", ctx=ast.Load()),
                args=[visited_obj, args_tuple, kwargs_dict],
                keywords=[ast.keyword(arg="method_name", value=ast.Constant(value=func_name))],
            )
            ast.copy_location(new_node, node)
            ast.fix_missing_locations(new_node)
            return new_node

        # For non-method calls, use generic_visit
        node = self.generic_visit(node)

        # Transform open() calls
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            self.needs_taint_imports = True
            new_node = ast.Call(
                func=ast.Name(id="taint_open", ctx=ast.Load()),
                args=node.args,
                keywords=node.keywords,
            )
            return ast.copy_location(new_node, node)

        # Transform direct function calls
        elif isinstance(node.func, ast.Name):
            self.needs_taint_imports = True

            func_node = ast.Name(id="exec_func", ctx=ast.Load())
            ast.copy_location(func_node, node)

            args_tuple = ast.Tuple(elts=node.args, ctx=ast.Load())
            ast.copy_location(args_tuple, node)

            kwargs_dict = ast.Dict(
                keys=[ast.Constant(value=kw.arg) if kw.arg else None for kw in node.keywords],
                values=[kw.value for kw in node.keywords],
            )
            ast.copy_location(kwargs_dict, node)

            for key in kwargs_dict.keys:
                if key is not None:
                    ast.copy_location(key, node)

            new_node = ast.Call(
                func=func_node,
                args=[node.func, args_tuple, kwargs_dict],
                keywords=[],
            )
            ast.copy_location(new_node, node)
            ast.fix_missing_locations(new_node)
            return new_node

        return node

    def visit_BinOp(self, node):
        """Transform binary operations into exec_func calls."""
        node = self.generic_visit(node)

        # Map AST operators to operator module functions
        op_mapping = {
            ast.Add: "add",
            ast.Sub: "sub",
            ast.Mult: "mul",
            ast.Div: "truediv",
            ast.FloorDiv: "floordiv",
            ast.Mod: "mod",
            ast.Pow: "pow",
            ast.LShift: "lshift",
            ast.RShift: "rshift",
            ast.BitOr: "or_",
            ast.BitXor: "xor",
            ast.BitAnd: "and_",
            ast.MatMult: "matmul",
        }

        # Special case: string % formatting
        if isinstance(node.op, ast.Mod) and (
            isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)
        ):
            self.needs_taint_imports = True
            new_node = ast.Call(
                func=ast.Name(id="get_attr", ctx=ast.Load()),
                args=[node.value, ast.Constant(value=node.attr)],
                keywords=[],
            )
            return ast.copy_location(new_node, node)

        # Handle all other binary operations
        op_type = type(node.op)
        if op_type in op_mapping:
            return self._create_exec_func_call(op_mapping[op_type], [node.left, node.right], node)

        return node

    def visit_UnaryOp(self, node):
        """Transform unary operations into exec_func calls (except 'not')."""
        node = self.generic_visit(node)

        # Skip 'not' to preserve control flow
        if isinstance(node.op, ast.Not):
            return node

        op_mapping = {ast.UAdd: "pos", ast.USub: "neg", ast.Invert: "invert"}

        op_type = type(node.op)
        if op_type in op_mapping:
            return self._create_exec_func_call(op_mapping[op_type], [node.operand], node)

        return node

    def visit_Compare(self, node):
        """Transform comparison operations into exec_func calls."""
        node = self.generic_visit(node)

        # Handle chained comparisons by breaking into binary comparisons
        if len(node.ops) > 1:
            # Transform a < b < c into (a < b) and (b < c)
            comparisons = []
            left = node.left

            for op, right in zip(node.ops, node.comparators):
                # Create and transform each binary comparison
                binary_compare = ast.Compare(left=left, ops=[op], comparators=[right])
                comparisons.append(self.visit_Compare(binary_compare))
                left = right  # Next comparison's left is current right

            # Connect with 'and' operations
            result = comparisons[0]
            for comp in comparisons[1:]:
                result = ast.BoolOp(op=ast.And(), values=[result, comp])

            return ast.copy_location(result, node)

        # Handle single comparisons
        if len(node.ops) == 1 and len(node.comparators) == 1:
            op_type = type(node.ops[0])

            # Standard operators that map directly to operator module functions
            standard_ops = {
                ast.Eq: "eq",
                ast.NotEq: "ne",
                ast.Lt: "lt",
                ast.LtE: "le",
                ast.Gt: "gt",
                ast.GtE: "ge",
            }

            if op_type in standard_ops:
                return self._create_exec_func_call(
                    standard_ops[op_type], [node.left, node.comparators[0]], node
                )

            # Identity comparisons: Don't transform - compare actual objects
            # (including TaintWrappers) without unwrapping
            elif op_type in (ast.Is, ast.IsNot):
                return node

            # Special case: 'in' - swap operands since contains(container, item)
            elif op_type == ast.In:
                return self._create_exec_func_call(
                    "contains", [node.comparators[0], node.left], node
                )

            # Special case: 'not in' - create lambda that negates contains
            elif op_type == ast.NotIn:
                op_func = ast.Lambda(
                    args=ast.arguments(
                        posonlyargs=[],
                        args=[ast.arg(arg="a", annotation=None), ast.arg(arg="b", annotation=None)],
                        vararg=None,
                        kwonlyargs=[],
                        kw_defaults=[],
                        kwarg=None,
                        defaults=[],
                    ),
                    body=ast.UnaryOp(
                        op=ast.Not(),
                        operand=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id="operator", ctx=ast.Load()),
                                attr="contains",
                                ctx=ast.Load(),
                            ),
                            args=[
                                ast.Name(id="b", ctx=ast.Load()),
                                ast.Name(id="a", ctx=ast.Load()),
                            ],
                            keywords=[],
                        ),
                    ),
                )
                return self._create_exec_func_call_custom(
                    op_func, [node.left, node.comparators[0]], node
                )

        return node

    def visit_AugAssign(self, node):
        """Transform augmented assignments (+=, -=, etc.) into exec_func calls."""
        node = self.generic_visit(node)

        op_mapping = {
            ast.Add: "iadd",
            ast.Sub: "isub",
            ast.Mult: "imul",
            ast.Div: "itruediv",
            ast.FloorDiv: "ifloordiv",
            ast.Mod: "imod",
            ast.Pow: "ipow",
            ast.LShift: "ilshift",
            ast.RShift: "irshift",
            ast.BitOr: "ior",
            ast.BitXor: "ixor",
            ast.BitAnd: "iand",
            ast.MatMult: "imatmul",
        }

        op_type = type(node.op)
        if op_type in op_mapping:
            return self._create_augassign_exec_func_call(
                op_mapping[op_type], node.target, node.value, node
            )

        return node

    def visit_Subscript(self, node):
        """Transform subscript reads (obj[key]) into get_item calls."""
        node = self.generic_visit(node)

        # Only transform Load context (obj[key])
        if isinstance(node.ctx, ast.Load):
            self.needs_taint_imports = True

            if isinstance(node.slice, ast.Slice):
                # For slices, create a slice object as the key
                slice_args = []
                if node.slice.lower is not None:
                    slice_args.append(node.slice.lower)
                else:
                    slice_args.append(ast.Constant(value=None))

                if node.slice.upper is not None:
                    slice_args.append(node.slice.upper)
                else:
                    slice_args.append(ast.Constant(value=None))

                if node.slice.step is not None:
                    slice_args.append(node.slice.step)

                slice_call = ast.Call(
                    func=ast.Name(id="slice", ctx=ast.Load()), args=slice_args, keywords=[]
                )
                # obj[start:end] -> get_item(obj, slice(start, end))
                new_node = ast.Call(
                    func=ast.Name(id="get_item", ctx=ast.Load()),
                    args=[node.value, slice_call],
                    keywords=[],
                )
            else:
                # obj[key] -> get_item(obj, key)
                new_node = ast.Call(
                    func=ast.Name(id="get_item", ctx=ast.Load()),
                    args=[node.value, node.slice],
                    keywords=[],
                )

            return ast.copy_location(new_node, node)

        return node

    def visit_Assign(self, node):
        """Transform all assignments to intercept taint propagation."""
        node = self.generic_visit(node)

        for target in node.targets:
            if isinstance(target, ast.Subscript):
                # obj[key] = value
                return self._create_subscript_exec_func_expr("setitem", target, node.value, node)
            elif isinstance(target, ast.Attribute):
                # obj.attr = value
                return self._create_attribute_assign_expr(target, node.value, node)
            elif isinstance(target, ast.Name):
                # a = value (simple variable assignment)
                return self._create_name_assign_expr(target, node.value, node)

        return node

    def visit_Delete(self, node):
        """Transform subscript deletions (del obj[key])."""
        node = self.generic_visit(node)

        for target in node.targets:
            if isinstance(target, ast.Subscript):
                return self._create_subscript_exec_func_expr("delitem", target, None, node)

        return node

    def _create_attribute_assign_expr(self, target, value, node):
        """Create set_attr call for attribute assignments (obj.attr = value)."""
        self.needs_taint_imports = True

        # obj.attr = value -> set_attr(obj, 'attr', value)
        assign_call = ast.Call(
            func=ast.Name(id="set_attr", ctx=ast.Load()),
            args=[target.value, ast.Constant(value=target.attr), value],
            keywords=[],
        )

        # Wrap in Expr since this is a statement
        new_node = ast.Expr(value=assign_call)
        return ast.copy_location(new_node, node)

    def _create_name_assign_expr(self, target, value, node):
        """Create assignment with taint_assign for name assignments (a = value)."""
        self.needs_taint_imports = True

        # x = value -> x = taint_assign(value)
        assign_call = ast.Call(
            func=ast.Name(id="taint_assign", ctx=ast.Load()),
            args=[value],
            keywords=[],
        )

        new_node = ast.Assign(targets=[target], value=assign_call)
        return ast.copy_location(new_node, node)

    def visit_Attribute(self, node):
        """Transform attribute reads (obj.attr) into get_attr calls."""
        node = self.generic_visit(node)

        # Only intercept Load context (reading attributes, not setting)
        if isinstance(node.ctx, ast.Load):
            self.needs_taint_imports = True
            # obj.attr -> get_attr(obj, 'attr')
            new_node = ast.Call(
                func=ast.Name(id="get_attr", ctx=ast.Load()),
                args=[node.value, ast.Constant(value=node.attr)],
                keywords=[],
            )
            return ast.copy_location(new_node, node)

        return node

    # NOTE: visit_Name is intentionally NOT implemented for Load context.
    # Variable reads don't need transformation - variables already hold wrappers from assignment.
    # When we do `x = value`, visit_Assign rewrites it to `x = taint_assign(value)`
    # which wraps the value. Later reading `x` just returns that wrapper directly.

    def _extract_project_root(self, current_file):
        """Extract project root by finding common prefix of module paths."""
        if not self.module_to_file:
            return None

        import os

        current_file = os.path.abspath(current_file)
        common_parts = None

        for file_path in self.module_to_file.values():
            file_path = os.path.abspath(file_path)
            if common_parts is None:
                common_parts = file_path.split(os.sep)
            else:
                path_parts = file_path.split(os.sep)
                common_parts = [
                    p
                    for i, p in enumerate(common_parts)
                    if i < len(path_parts) and path_parts[i] == p
                ]

        if common_parts:
            return os.sep.join(common_parts) or os.sep
        return None

    def _inject_taint_imports(self, tree):
        """Inject import statements for taint functions if needed."""
        if not self.needs_taint_imports:
            return tree

        insertion_point = 0
        last_future_import_pos = -1

        for i, node in enumerate(tree.body):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                last_future_import_pos = i

        if last_future_import_pos >= 0:
            insertion_point = last_future_import_pos + 1

        safe_import_code = """
import operator
from ao.server.ast_helpers import exec_func, exec_setitem, exec_delitem, exec_inplace_binop, taint_fstring_join, taint_format_string, taint_percent_format, taint_open, taint_assign, get_attr, get_item, set_attr
"""

        safe_import_tree = ast.parse(safe_import_code)

        for i, node in enumerate(safe_import_tree.body):
            tree.body.insert(insertion_point + i, node)

        return tree
