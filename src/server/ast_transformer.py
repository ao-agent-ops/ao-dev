"""
AST transformation for taint tracking.

Rewrites Python code to track data flow by wrapping operations with taint-aware functions:

1. String formatting: f-strings, .format(), % -> taint_fstring_join, taint_format_string, taint_percent_format
2. Function calls: All functions and methods -> exec_func (except dunder methods)
3. Operations: +, -, *, [], +=, etc. -> exec_func with operator functions
4. File operations: open() -> taint_open with database persistence

exec_func determines at runtime whether to apply taint (third-party code) or call normally (user code).
"""

import ast
from aco.runner.taint_wrappers import TaintWrapper, get_taint_origins, untaint_if_needed, taint_wrap
from aco.common.utils import get_aco_py_files, hash_input
# from aco.server.ast_transformer_helpers import *


# ===================================================
# Helpers
# ===================================================

from dill import PicklingError, dumps
from inspect import getsourcefile, iscoroutinefunction
from aco.runner.taint_wrappers import get_taint_origins, untaint_if_needed, taint_wrap
import ast


def _unified_taint_string_operation(operation_func, *inputs):
    """
    Unified helper for all taint-aware string operations.
    
    Args:
        operation_func: Function that performs the actual string operation on untainted inputs
        *inputs: All inputs that may contain taint (format strings, values, etc.)
        
    Returns:
        str or TaintWrapper: Result with taint information preserved
    """
    # Collect taint origins from all inputs
    all_origins = set()
    for inp in inputs:
        if isinstance(inp, (tuple, list)):
            # Handle tuple/list inputs (like values in % formatting)
            for item in inp:
                all_origins.update(get_taint_origins(item))
        elif isinstance(inp, dict):
            # Handle dict inputs (like kwargs in .format())
            for value in inp.values():
                all_origins.update(get_taint_origins(value))
        else:
            # Handle single values
            all_origins.update(get_taint_origins(inp))
    
    # Call the operation function with untainted inputs
    result = operation_func(*[untaint_if_needed(inp) for inp in inputs])
    
    # Return tainted result if any origins exist
    if all_origins:
        return TaintWrapper(result, list(all_origins))
    return result


def taint_fstring_join(*args):
    """Taint-aware replacement for f-string concatenation."""
    def join_operation(*unwrapped_args):
        return "".join(str(arg) for arg in unwrapped_args)
    
    return _unified_taint_string_operation(join_operation, *args)


def taint_format_string(format_string, *args, **kwargs):
    """Taint-aware replacement for .format() string method calls."""
    def format_operation(unwrapped_format_string, *unwrapped_args, **unwrapped_kwargs):
        return unwrapped_format_string.format(*unwrapped_args, **unwrapped_kwargs)
    
    return _unified_taint_string_operation(format_operation, format_string, args, kwargs)


def taint_percent_format(format_string, values):
    """Taint-aware replacement for % string formatting operations."""
    def percent_operation(unwrapped_format_string, unwrapped_values):
        return unwrapped_format_string % unwrapped_values
    
    return _unified_taint_string_operation(percent_operation, format_string, values)


def taint_open(*args, **kwargs):
    """Taint-aware replacement for open() that returns persistence-enabled TaintWrapper."""
    # Extract filename for default taint origin
    if args and len(args) >= 1:
        filename = args[0]
    else:
        filename = kwargs.get('file') or kwargs.get('filename')
    
    # Call the original open
    file_obj = open(*args, **kwargs)
    
    # Create default taint origin from filename
    default_taint = f"file:{filename}" if filename else "file:unknown"
    
    # Return TaintWrapper with persistence enabled
    return TaintWrapper(file_obj, taint_origin=[default_taint], enable_persistence=True)


def _is_user_function(func):
    """
    Check if function is user code (skip taint) or third-party (apply taint).
    
    Handles decorated functions by unwrapping via __wrapped__ attribute.
    """
    # Determine user files dynamically
    import os
    user_py_files = []
    
    # Try to get project root from environment (set by launch scripts)
    project_root = os.environ.get("AGENT_COPILOT_PROJECT_ROOT")
    if project_root:
        # Scan project root for Python files
        try:
            from aco.common.utils import scan_user_py_files_and_modules
            module_to_file = scan_user_py_files_and_modules(project_root)
            user_py_files = list(module_to_file.values())
        except Exception:
            pass
    
    # Always include ACO files as user files
    user_py_files.extend(get_aco_py_files())
    
    if not user_py_files:
        # No user files found, must be third-party
        return False

    # Strategy 1: Direct source file check (handles undecorated functions)
    try:
        source_file = getsourcefile(func)
    except TypeError:
        # Built-in function or function without source file
        return False

    if source_file and source_file in user_py_files:
        return True

    # Strategy 2: Check __wrapped__ attribute (functools.wraps pattern)
    # This handles most well-behaved decorators including @retry, @lru_cache, etc.
    current_func = func
    max_unwrap_depth = 10  # Prevent infinite loops
    depth = 0

    while hasattr(current_func, "__wrapped__") and depth < max_unwrap_depth:
        current_func = current_func.__wrapped__
        depth += 1

        try:
            source_file = getsourcefile(current_func)
            if source_file and source_file in user_py_files:
                return True
        except TypeError:
            return False

    return False


def _get_bound_obj_hash(bound_self: object | None):
    """Get the hash of a bound object, returning None if the object is unhashable.

    Args:
        bound_self: The object to hash, typically a bound method's self argument.

    Returns:
        The hash of the object if hashable, None otherwise.
    """
    bound_hash = None
    if bound_self:
        try:
            bytes_string = dumps(bound_self)
        except (PicklingError, TypeError):
            try:
                bound_hash = hash_input(bound_self)
            except Exception:
                pass
        else:
            bound_hash = hash_input(bytes_string)
    return bound_hash


def _is_type_annotation_access(obj, key):
    """
    Detect if this getitem call is for type annotation rather than runtime access.
    
    Args:
        obj: The object being subscripted
        key: The key/index being accessed
        
    Returns:
        bool: True if this looks like a type annotation access (e.g., Dict[str, int])
    """
    # Check 1: Is the object a type/class rather than an instance?
    if isinstance(obj, type):
        return True
    
    # Check 2: Is it from typing module?
    if hasattr(obj, '__module__') and obj.__module__ == 'typing':
        return True
    
    # Check 3: Is it a generic alias (Python 3.9+)?
    if hasattr(obj, '__origin__'):  # GenericAlias objects like list[int]
        return True
    
    # Check 4: Does it support generic subscripting (__class_getitem__)?
    if hasattr(obj, '__class_getitem__'):
        # Make sure it's not a regular dict/list/set with custom __class_getitem__
        obj_type_name = type(obj).__name__
        if obj_type_name in {'dict', 'list', 'tuple', 'set'}:
            # This is a runtime collection instance, not a type
            return False
        # Likely a generic type that supports subscripting
        return True
    
    # Check 5: Common type constructs by name
    if hasattr(obj, '__name__'):
        type_names = {'Dict', 'List', 'Tuple', 'Set', 'Optional', 'Union', 'Any', 'Callable'}
        if obj.__name__ in type_names:
            return True
    
    return False


def _prepare_function_call(func, args, kwargs):
    """
    Prepare function call by collecting taint and processing arguments.
    
    Returns:
        dict: Call preparation info for handling the function call
    """
    # Collect taint from all arguments before unwrapping
    all_origins = set()
    all_origins.update(get_taint_origins(args))
    all_origins.update(get_taint_origins(kwargs))
    
    # Extract taint from bound methods (self.__self__)
    bound_self = None
    if hasattr(func, "__self__"):
        bound_self = func.__self__
    elif hasattr(func, "func") and hasattr(func.func, "__self__"):
        # Handle functools.partial objects
        bound_self = func.func.__self__
    
    if bound_self is not None:
        all_origins.update(get_taint_origins(bound_self))
    
    # Special handling for file operations with persistence
    if bound_self and getattr(bound_self, '_enable_persistence', False):
        # This is handled separately, return special marker
        return {'file_operation': True, 'bound_self': bound_self, 'all_origins': all_origins}
    
    # Untaint arguments for the function call
    untainted_args = untaint_if_needed(args)
    untainted_kwargs = untaint_if_needed(kwargs)
    
    # Check if this is a type annotation access (e.g., Dict[str, int])
    if (hasattr(func, '__name__') and func.__name__ == 'getitem' and 
        len(untainted_args) >= 2):
        obj, key = untainted_args[0], untainted_args[1]
        if _is_type_annotation_access(obj, key):
            # Call normally without taint propagation
            return {'type_annotation': True, 'untainted_args': untainted_args, 'untainted_kwargs': untainted_kwargs}
    
    # Prepare side effect detection
    bound_hash_before = _get_bound_obj_hash(bound_self) if all_origins else None
    
    # Create untainted version of bound_self if present
    untainted_bound_self = None
    if bound_self is not None:
        untainted_bound_self = untaint_if_needed(bound_self)
    
    return {
        'all_origins': all_origins,
        'bound_self': bound_self,
        'untainted_bound_self': untainted_bound_self,
        'untainted_args': untainted_args,
        'untainted_kwargs': untainted_kwargs,
        'bound_hash_before': bound_hash_before,
        'original_args': args,
        'original_kwargs': kwargs
    }


def _finalize_function_call(result, call_info, func):
    """
    Finalize function call by updating taint and wrapping result.
    """
    all_origins = call_info['all_origins']
    bound_self = call_info['bound_self']
    bound_hash_before = call_info['bound_hash_before']
    
    # Detect side effects
    bound_hash_after = _get_bound_obj_hash(bound_self) if all_origins else None
    no_side_effect = (
        bound_hash_before is not None
        and bound_hash_after is not None
        and bound_hash_before == bound_hash_after
    )
    
    # Update bound object taint from inputs
    if bound_self is not None and hasattr(bound_self, "_taint_origin"):
        input_taint = set()
        input_taint.update(get_taint_origins(call_info['original_args']))
        input_taint.update(get_taint_origins(call_info['original_kwargs']))
        
        if input_taint:
            try:
                current_origins = object.__getattribute__(bound_self, "_taint_origin")
                new_origins = set(current_origins) | input_taint
                object.__setattr__(bound_self, "_taint_origin", list(new_origins))
            except (AttributeError, TypeError):
                pass
    
    # Wrap result with taint if there is any
    if all_origins:
        if no_side_effect:
            return taint_wrap(result, taint_origin=all_origins)
        
        # Taint bound object as well
        if hasattr(func, "__self__"):
            taint_wrap(bound_self, taint_origin=all_origins)
        elif hasattr(func, "func") and hasattr(func.func, "__self__"):
            taint_wrap(bound_self, taint_origin=all_origins)
        
        return taint_wrap(result, taint_origin=all_origins)
    
    return result


def exec_func(func, args, kwargs):
    """
    Execute function with runtime user/third-party detection.
    
    User code: called normally (no taint overhead), with fallback to unwrapping if needed
    Third-party code: full taint propagation
    """
    # Debug breakpoint for TaskTracer.model_dump_json
    if (hasattr(func, '__name__') and func.__name__ == 'model_dump_json' and 
        hasattr(func, '__self__') and type(func.__self__).__name__ == 'TaskTracer'):
        pass  # Set breakpoint here
    
    if iscoroutinefunction(func):
        async def wrapper():
            # Try user code path first
            if _is_user_function(func):
                try:
                    # User code - call directly
                    return await func(*args, **kwargs)
                except:
                    # Fall through to handle as third-party (unwrap args)
                    pass
            
            # Prepare the function call (shared logic)
            call_info = _prepare_function_call(func, args, kwargs)
            
            # Handle special cases
            if call_info.get('file_operation'):
                # File operation with persistence
                return _handle_persistent_file_operation(
                    call_info['bound_self'], func, args, kwargs, call_info['all_origins']
                )
            elif call_info.get('type_annotation'):
                # Type annotation access
                return func(*call_info['untainted_args'], **call_info['untainted_kwargs'])
            
            # Normal third-party function call
            # If we have a bound method, recreate it with untainted self
            func_to_call = func
            if call_info['untainted_bound_self'] is not None and hasattr(func, '__func__'):
                # Recreate bound method with untainted self
                func_to_call = func.__func__.__get__(call_info['untainted_bound_self'], type(call_info['untainted_bound_self']))
            
            result = await func_to_call(*call_info['untainted_args'], **call_info['untainted_kwargs'])
            return _finalize_function_call(result, call_info, func)
        
        return wrapper()
    
    # Sync version - same logic, no await
    # Try user code path first
    if _is_user_function(func):
        try:
            # User code - call directly
            return func(*args, **kwargs)
        except:
            print("~~ caused exception, retry")
            # Fall through to handle as third-party (unwrap args)
            pass
    
    call_info = _prepare_function_call(func, args, kwargs)
    
    # Handle special cases
    if call_info.get('file_operation'):
        # File operation with persistence
        return _handle_persistent_file_operation(
            call_info['bound_self'], func, args, kwargs, call_info['all_origins']
        )
    elif call_info.get('type_annotation'):
        # Type annotation access
        return func(*call_info['untainted_args'], **call_info['untainted_kwargs'])
    
    # Normal third-party function call
    # If we have a bound method, recreate it with untainted self
    func_to_call = func
    if call_info['untainted_bound_self'] is not None and hasattr(func, '__func__'):
        # Recreate bound method with untainted self
        func_to_call = func.__func__.__get__(call_info['untainted_bound_self'], type(call_info['untainted_bound_self']))
    
    result = func_to_call(*call_info['untainted_args'], **call_info['untainted_kwargs'])
    return _finalize_function_call(result, call_info, func)


def _handle_persistent_file_operation(bound_self, func, args, kwargs, all_origins):
    """Handle file operations with database persistence."""
    # Handle functools.partial objects from TaintWrapper.__getattr__
    if hasattr(func, 'func') and hasattr(func, 'args') and hasattr(func, 'keywords'):
        # This is a functools.partial object from TaintWrapper.bound_method
        # The method name is the second argument to bound_method
        if func.args and len(func.args) >= 1:
            method_name = func.args[0]  # The method name passed to bound_method
        else:
            method_name = "unknown"
    else:
        method_name = getattr(func, '__name__', 'unknown')
    
    if method_name == 'write':
        return _handle_file_write(bound_self, func, args, kwargs, all_origins)
    elif method_name in ['read', 'readline']:
        return _handle_file_read(bound_self, func, args, kwargs, all_origins, method_name)
    elif method_name == 'writelines':
        return _handle_file_writelines(bound_self, func, args, kwargs, all_origins)
    else:
        # All other file methods: just call normally and propagate taint
        untainted_args = untaint_if_needed(args)
        untainted_kwargs = untaint_if_needed(kwargs) 
        result = func(*untainted_args, **untainted_kwargs)
        if all_origins:
            return taint_wrap(result, taint_origin=all_origins)
        return result


def _handle_file_write(bound_self, func, args, kwargs, all_origins):
    """Handle file write operations with DB storage."""
    from aco.server.database_manager import DB
    
    session_id = object.__getattribute__(bound_self, "_session_id")
    line_no = object.__getattribute__(bound_self, "_line_no")
    file_obj = object.__getattribute__(bound_self, "obj")
    
    # Get the data being written (first argument)
    data = args[0] if args else None
    if data is None:
        return func(*args, **kwargs)
    
    # Untaint the data for the actual write operation
    untainted_data = untaint_if_needed(data)
    untainted_args = (untainted_data,) + args[1:] if len(args) > 1 else (untainted_data,)
    untainted_kwargs = untaint_if_needed(kwargs)
    
    # Store taint information in database if we have session ID and filename
    if session_id and hasattr(file_obj, "name"):
        taint_nodes = get_taint_origins(data)
        if taint_nodes:
            try:
                DB.store_taint_info(session_id, file_obj.name, line_no, taint_nodes)
            except Exception as e:
                import sys
                print(f"Warning: Could not store taint info: {e}", file=sys.stderr)
        
        # Update line number
        newline_count = untainted_data.count("\n") if isinstance(untainted_data, str) else 0
        object.__setattr__(bound_self, "_line_no", line_no + max(1, newline_count))
    
    # Perform the actual write (works for both regular methods and functools.partial)
    result = func(*untainted_args, **untainted_kwargs)
    
    # Write operations typically return number of bytes written or None
    return result


def _handle_file_read(bound_self, func, args, kwargs, all_origins, method_name=None):
    """Handle file read operations with DB retrieval."""
    from aco.server.database_manager import DB
    
    session_id = object.__getattribute__(bound_self, "_session_id")
    line_no = object.__getattribute__(bound_self, "_line_no")
    file_obj = object.__getattribute__(bound_self, "obj")
    taint_origin = object.__getattribute__(bound_self, "_taint_origin")
    
    # Untaint arguments for the actual read operation
    untainted_args = untaint_if_needed(args)
    untainted_kwargs = untaint_if_needed(kwargs)
    
    # Perform the actual read (works for both regular methods and functools.partial)
    data = func(*untainted_args, **untainted_kwargs)
    
    if isinstance(data, bytes):
        # For binary mode, return as-is (could extend this later)
        return data
    
    # Check for existing taint from previous sessions
    combined_taint = list(taint_origin)  # Start with file's default taint
    
    if hasattr(file_obj, "name") and data:
        try:
            prev_session_id, stored_taint_nodes = DB.get_taint_info(file_obj.name, line_no)
            if prev_session_id and stored_taint_nodes:
                # Combine existing taint with stored taint
                combined_taint.extend(stored_taint_nodes)
                combined_taint = list(set(combined_taint))  # Remove duplicates
        except Exception as e:
            import sys
            print(f"Warning: Could not retrieve taint info: {e}", file=sys.stderr)
    
    # Update line number for readline
    if method_name == 'readline':
        object.__setattr__(bound_self, "_line_no", line_no + 1)
    
    # Return tainted data
    if combined_taint:
        return taint_wrap(data, taint_origin=combined_taint)
    return data


def _handle_file_writelines(bound_self, func, args, kwargs, all_origins):
    """Handle file writelines operations with DB storage."""
    from aco.server.database_manager import DB
    
    session_id = object.__getattribute__(bound_self, "_session_id")
    line_no = object.__getattribute__(bound_self, "_line_no")
    file_obj = object.__getattribute__(bound_self, "obj")
    
    # Get the lines being written (first argument)
    lines = args[0] if args else None
    if lines is None:
        return func(*args, **kwargs)
    
    # Process each line for taint storage and untainting
    untainted_lines = []
    current_line = line_no
    
    for line in lines:
        # Store taint for each line
        if session_id and hasattr(file_obj, "name"):
            taint_nodes = get_taint_origins(line)
            if taint_nodes:
                try:
                    DB.store_taint_info(session_id, file_obj.name, current_line, taint_nodes)
                except Exception as e:
                    import sys
                    print(f"Warning: Could not store taint info: {e}", file=sys.stderr)
        
        current_line += 1
        untainted_lines.append(untaint_if_needed(line))
    
    # Update the line number on the wrapper
    object.__setattr__(bound_self, "_line_no", current_line)
    
    # Untaint arguments
    untainted_args = (untainted_lines,) + args[1:] if len(args) > 1 else (untainted_lines,)
    untainted_kwargs = untaint_if_needed(kwargs)
    
    # Perform the actual writelines (works for both regular methods and functools.partial)
    result = func(*untainted_args, **untainted_kwargs)
    return result


# ===================================================
# Transformer
# ===================================================
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
        # also include all files in agent-copilot
        self.user_py_files.extend(get_aco_py_files())
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
            value=ast.Name(id='operator', ctx=ast.Load()),
            attr=op_func_name,
            ctx=ast.Load()
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
        """Create assignment with exec_func call for augmented assignment operations."""
        self.needs_taint_imports = True
        
        # Create a copy of target with Load context for use in args
        import copy
        target_load = copy.deepcopy(target)
        if hasattr(target_load, 'ctx'):
            target_load.ctx = ast.Load()
        # Recursively fix context for nested attributes/subscripts
        for child in ast.walk(target_load):
            if hasattr(child, 'ctx') and not isinstance(child.ctx, ast.Load):
                child.ctx = ast.Load()

        # Create exec_func call
        exec_func_call = self._create_exec_func_call(op_func_name, [target_load, value], node)
        
        # Transform into assignment: target = exec_func(...)
        new_node = ast.Assign(
            targets=[target],
            value=exec_func_call
        )
        
        return ast.copy_location(new_node, node)

    def _create_subscript_exec_func_expr(self, op_func_name, target, value, node):
        """Create Expr with exec_func call for subscript assignment/deletion operations."""
        self.needs_taint_imports = True
        
        # Create copies with Load context
        import copy
        target_value_load = copy.deepcopy(target.value)
        target_slice_load = copy.deepcopy(target.slice)
        
        # Fix context for all nodes in the copies
        for child in ast.walk(target_value_load):
            if hasattr(child, 'ctx'):
                child.ctx = ast.Load()
        for child in ast.walk(target_slice_load):
            if hasattr(child, 'ctx'):
                child.ctx = ast.Load()
        
        # Create args list
        if value is not None:
            args_list = [target_value_load, target_slice_load, value]
        else:
            args_list = [target_value_load, target_slice_load]
        
        # Create exec_func call and wrap in Expr
        exec_func_call = self._create_exec_func_call(op_func_name, args_list, node)
        new_node = ast.Expr(value=exec_func_call)
        
        return ast.copy_location(new_node, node)

    def visit_JoinedStr(self, node):
        """
        Transform f-string literals into taint_fstring_join calls.

        Converts f-string expressions like f"Hello {name}!" into equivalent
        function calls that preserve taint information.

        Args:
            node (ast.JoinedStr): The f-string AST node to transform

        Returns:
            ast.Call: A call to taint_fstring_join with the f-string components as arguments
        """
        # Mark that we need taint imports
        self.needs_taint_imports = True

        # Transform each component of the f-string
        args = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                # String literal part - keep as is
                args.append(value)
            elif isinstance(value, ast.FormattedValue):
                # Expression part - extract the expression and recursively transform it
                transformed_value = self.visit(value.value)
                args.append(transformed_value)
            else:
                # Other types - recursively transform
                transformed_value = self.visit(value)
                args.append(transformed_value)

        # Replace f-string with a call to taint_fstring_join
        new_node = ast.Call(
            func=ast.Name(id="taint_fstring_join", ctx=ast.Load()),
            args=args,
            keywords=[],
        )
        return ast.copy_location(new_node, node)

    def visit_Call(self, node):
        """
        Transform function calls to exec_func, taint_format_string, or taint_open.
        
        Skips dunder methods. All other calls wrapped with exec_func.
        """
        # First, recursively visit child nodes
        node = self.generic_visit(node)

        # Check if this is a .format() call on any expression
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            # Mark that we need taint imports
            self.needs_taint_imports = True

            # Transform .format() call -> taint_format_string
            new_node = ast.Call(
                func=ast.Name(id="taint_format_string", ctx=ast.Load()),
                args=[node.func.value] + node.args,
                keywords=node.keywords,
            )
            return ast.copy_location(new_node, node)

        # Check if this is a method call (module.function() or obj.method())
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            func_name = node.func.attr

            # Skip dunder methods - never wrap these
            dunder_methods = {
                "__init__",
                "__new__",
                "__del__",
                "__repr__",
                "__str__",
                "__bytes__",
                "__format__",
                "__lt__",
                "__le__",
                "__eq__",
                "__ne__",
                "__gt__",
                "__ge__",
                "__hash__",
                "__bool__",
                "__getitem__",
                "__setitem__",
                "__delitem__",
                "__len__",
                "__iter__",
                "__reversed__",
                "__contains__",
                "__enter__",
                "__exit__",
                "__call__",
                "__getattr__",
                "__setattr__",
            }
            if func_name in dunder_methods:
                return node

            # Mark that we need taint imports
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

            # Fix missing locations on key constants
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

        # Check if this is an open() call
        elif isinstance(node.func, ast.Name) and node.func.id == "open":
            # Mark that we need taint imports
            self.needs_taint_imports = True
            
            # Transform open() to taint_open()
            new_node = ast.Call(
                func=ast.Name(id="taint_open", ctx=ast.Load()),
                args=node.args,
                keywords=node.keywords,
            )
            return ast.copy_location(new_node, node)

        # Check if this is a direct function call (function_name())
        elif isinstance(node.func, ast.Name):
            # Mark that we need taint imports
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

            # Fix missing locations on key constants
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
            ast.Add: 'add', ast.Sub: 'sub', ast.Mult: 'mul', ast.Div: 'truediv',
            ast.FloorDiv: 'floordiv', ast.Mod: 'mod', ast.Pow: 'pow',
            ast.LShift: 'lshift', ast.RShift: 'rshift', ast.BitOr: 'or_',
            ast.BitXor: 'xor', ast.BitAnd: 'and_', ast.MatMult: 'matmul'
        }

        # Special case: string % formatting
        if isinstance(node.op, ast.Mod) and (
            isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)
        ):
            self.needs_taint_imports = True
            new_node = ast.Call(
                func=ast.Name(id="taint_percent_format", ctx=ast.Load()),
                args=[node.left, node.right],
                keywords=[],
            )
            return ast.copy_location(new_node, node)

        # Handle all other binary operations
        op_type = type(node.op)
        if op_type in op_mapping:
            return self._create_exec_func_call(op_mapping[op_type], [node.left, node.right], node)

        return node

    def visit_UnaryOp(self, node):
        """Transform unary operations into exec_func calls. Skips 'not' for control flow."""
        node = self.generic_visit(node)

        # Don't transform 'not' since it should return plain bool for control flow
        if isinstance(node.op, ast.Not):
            return node

        # Map AST unary operators to operator module functions
        op_mapping = {
            ast.UAdd: 'pos',        # +x
            ast.USub: 'neg',        # -x
            ast.Invert: 'invert'    # ~x
        }

        op_type = type(node.op)
        if op_type in op_mapping:
            return self._create_exec_func_call(op_mapping[op_type], [node.operand], node)

        return node

    def visit_Compare(self, node):
        """Transform comparison operations into exec_func calls."""
        node = self.generic_visit(node)

        # Only handle single comparisons for now (a < b, not a < b < c)
        if len(node.ops) == 1 and len(node.comparators) == 1:
            op_type = type(node.ops[0])
            
            # Standard operators that map directly to operator module functions
            standard_ops = {
                ast.Eq: 'eq', ast.NotEq: 'ne', ast.Lt: 'lt', ast.LtE: 'le',
                ast.Gt: 'gt', ast.GtE: 'ge', ast.Is: 'is_', ast.IsNot: 'is_not'
            }
            
            if op_type in standard_ops:
                return self._create_exec_func_call(standard_ops[op_type], [node.left, node.comparators[0]], node)
            
            # Special case: 'in' - swap operands since contains(container, item)  
            elif op_type == ast.In:
                return self._create_exec_func_call('contains', [node.comparators[0], node.left], node)
            
            # Special case: 'not in' - create lambda that negates contains
            elif op_type == ast.NotIn:
                op_func = ast.Lambda(
                    args=ast.arguments(
                        posonlyargs=[], args=[
                            ast.arg(arg='a', annotation=None),
                            ast.arg(arg='b', annotation=None)
                        ],
                        vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]
                    ),
                    body=ast.UnaryOp(
                        op=ast.Not(),
                        operand=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(id='operator', ctx=ast.Load()),
                                attr='contains',
                                ctx=ast.Load()
                            ),
                            args=[ast.Name(id='b', ctx=ast.Load()), ast.Name(id='a', ctx=ast.Load())],
                            keywords=[]
                        )
                    )
                )
                return self._create_exec_func_call_custom(op_func, [node.left, node.comparators[0]], node)

        return node

    def visit_AugAssign(self, node):
        """Transform augmented assignments (+=, -=, etc.) into assignments with exec_func calls."""
        node = self.generic_visit(node)

        # Map AST augmented assignment operators to operator module functions
        op_mapping = {
            ast.Add: 'iadd', ast.Sub: 'isub', ast.Mult: 'imul', ast.Div: 'itruediv',
            ast.FloorDiv: 'ifloordiv', ast.Mod: 'imod', ast.Pow: 'ipow',
            ast.LShift: 'ilshift', ast.RShift: 'irshift', ast.BitOr: 'ior',
            ast.BitXor: 'ixor', ast.BitAnd: 'iand', ast.MatMult: 'imatmul'
        }

        op_type = type(node.op)
        if op_type in op_mapping:
            return self._create_augassign_exec_func_call(op_mapping[op_type], node.target, node.value, node)

        return node

    def visit_Subscript(self, node):
        """Transform subscript operations (obj[key]) into exec_func calls."""
        node = self.generic_visit(node)

        # Only transform subscript operations in Load context (obj[key])
        # Store (obj[key] = value) and Del (del obj[key]) contexts are handled differently
        if isinstance(node.ctx, ast.Load):
            # Special handling for slice objects - convert to slice() call
            if isinstance(node.slice, ast.Slice):
                # Create a slice() call with the appropriate arguments
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
                
                # Create slice() call node
                slice_call = ast.Call(
                    func=ast.Name(id='slice', ctx=ast.Load()),
                    args=slice_args,
                    keywords=[]
                )
                return self._create_exec_func_call('getitem', [node.value, slice_call], node)
            else:
                # For regular subscripts (not slices), use the slice directly
                return self._create_exec_func_call('getitem', [node.value, node.slice], node)

        return node

    def visit_Assign(self, node):
        """Transform assignment operations involving subscripts (obj[key] = value)."""
        node = self.generic_visit(node)

        # Check if any target is a subscript operation
        for target in node.targets:
            if isinstance(target, ast.Subscript):
                return self._create_subscript_exec_func_expr('setitem', target, node.value, node)

        return node

    def visit_Delete(self, node):
        """Transform delete operations involving subscripts (del obj[key])."""
        node = self.generic_visit(node)

        # Check if any target is a subscript operation
        for target in node.targets:
            if isinstance(target, ast.Subscript):
                return self._create_subscript_exec_func_expr('delitem', target, None, node)

        return node


    def _extract_project_root(self, current_file):
        """Extract project root by finding common prefix of module paths."""
        if not self.module_to_file:
            return None

        import os

        current_file = os.path.abspath(current_file)

        # Find common prefix of all module files with current file
        common_parts = None
        for file_path in self.module_to_file.values():
            file_path = os.path.abspath(file_path)
            if common_parts is None:
                common_parts = file_path.split(os.sep)
            else:
                path_parts = file_path.split(os.sep)
                # Keep only common prefix
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

        # Find the insertion point after any __future__ imports
        insertion_point = 0
        has_future_imports = False
        last_future_import_pos = -1

        for i, node in enumerate(tree.body):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                has_future_imports = True
                last_future_import_pos = i
                # Check if annotations is already imported
                if any(alias.name == "annotations" for alias in (node.names or [])):
                    has_annotations_import = True

        if has_future_imports:
            # Insert after the last __future__ import
            insertion_point = last_future_import_pos + 1
        else:
            # Insert at the beginning if no __future__ imports
            insertion_point = 0


        # Create safe import with fallbacks for plain Python execution
        safe_import_code = """
import operator
from aco.server.ast_transformer import exec_func, taint_fstring_join, taint_format_string, taint_percent_format, taint_open
"""

        # Parse the safe import code and inject it
        safe_import_tree = ast.parse(safe_import_code)

        # Insert all nodes from the safe import at the proper insertion point
        for i, node in enumerate(safe_import_tree.body):
            tree.body.insert(insertion_point + i, node)

        return tree