"""
Unified AST transformation for comprehensive taint tracking.

This module provides a single, efficient AST transformer that rewrites all
taint-relevant operations in Python code through a single AST traversal:

1. String formatting operations:
   - F-strings (f"...{expr}...") -> taint_fstring_join calls
   - .format() calls ("...{}...".format(args)) -> taint_format_string calls
   - % formatting ("...%s..." % values) -> taint_percent_format calls

2. Third-party library function calls:
   - Library calls (re.search, json.dumps, etc.) -> exec_func wrapped calls
   - Only wraps functions from outside the project (third-party code)
   - Skips user-defined functions and dunder methods

Key Components:
- TaintPropagationTransformer: Unified AST transformer for all taint operations
- taint_fstring_join: Taint-aware replacement for f-string concatenation
- taint_format_string: Taint-aware replacement for .format() calls
- taint_percent_format: Taint-aware replacement for % formatting
- exec_func: Generic taint-aware function executor for third-party calls

Performance Benefits:
- Single AST traversal instead of multiple passes
- Reduced overhead and better cache locality
- Conceptually cleaner organization of all taint transformations

The transformer preserves taint information and tracking through both string and
function operations, ensuring sensitive data remains tainted throughout execution.
"""

import ast
from dill import PicklingError, dumps
from json import dumps as json_dumps
from inspect import getsourcefile, iscoroutinefunction, isbuiltin
from aco.runner.taint_wrappers import TaintStr, get_taint_origins, untaint_if_needed, taint_wrap
from aco.common.utils import get_aco_py_files, hash_input
from aco.common.logger import logger


def is_pyc_rewritten(pyc_path: str) -> bool:
    """
    Check if a .pyc file was created by our AST transformer.

    Args:
        pyc_path: Path to a .pyc file

    Returns:
        True if the .pyc contains our rewrite marker, False otherwise
    """
    try:
        import marshal

        with open(pyc_path, "rb") as f:
            # Skip the .pyc header (magic number, flags, timestamp, size)
            f.read(16)
            code = marshal.load(f)

            # Check if our marker is in the code object's names or constants
            return "__ACO_AST_REWRITTEN__" in code.co_names
    except (IOError, OSError, Exception) as e:
        logger.error(f"Error is_pyc_rewritten: {e}")
        return False


def rewrite_source_to_code(source: str, filename: str, module_to_file: dict = None):
    """
    Transform and compile Python source code with AST rewrites.

    This is a pure function that applies AST transformations and compiles
    the result to a code object. Same input always produces same output,
    making it suitable for caching.

    Args:
        source: Python source code as a string
        filename: Path to the source file (used in error messages and code object)
        module_to_file: Dict mapping user module names to their file paths.
                       Used to distinguish user code from third-party code.

    Returns:
        A compiled code object ready for execution

    Raises:
        SyntaxError: If the source code is invalid
        Exception: If AST transformation fails
    """
    # Parse source into AST
    tree = ast.parse(source, filename=filename)

    # Add rewrite marker after any __future__ imports
    # This allows us to verify that a .pyc file was created by our AST transformer
    marker = ast.Assign(
        targets=[ast.Name(id="__ACO_AST_REWRITTEN__", ctx=ast.Store())],
        value=ast.Constant(value=True),
    )

    # Find insertion point after any __future__ imports
    insertion_point = 0
    for i, node in enumerate(tree.body):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            insertion_point = i + 1

    # Set location info for the marker to line 0 to hide from debugger
    marker.lineno = 0
    marker.col_offset = 0
    for node in ast.walk(marker):
        if hasattr(node, "lineno"):
            node.lineno = 0
        if hasattr(node, "col_offset"):
            node.col_offset = 0
    tree.body.insert(insertion_point, marker)

    # Apply AST transformations for taint propagation
    # Unified transformer handles: f-strings, .format(), % formatting, and third-party calls
    transformer = TaintPropagationTransformer(module_to_file=module_to_file, current_file=filename)
    tree = transformer.visit(tree)

    # Inject taint function imports if any transformations were made
    tree = transformer._inject_taint_imports(tree)

    # Fix missing location information
    ast.fix_missing_locations(tree)

    # Compile to code object
    code_object = compile(tree, filename, "exec")

    return code_object


def taint_fstring_join(*args):
    """
    Taint-aware replacement for f-string concatenation.

    This function is used as a runtime replacement for f-string expressions.
    It joins the provided arguments into a single string while preserving
    taint information and tracking positional data from tainted sources.

    The function:
    1. Collects taint origins from all arguments
    2. Unwraps all arguments to get raw values
    3. Joins all arguments into a single string
    4. Returns a TaintStr with collected taint origins if any taint exists

    Args:
        *args: Variable number of arguments to join (values from f-string expressions)

    Returns:
        str or TaintStr: The joined string with taint information preserved

    Example:
        # Original: f"Hello {name}, you have {count} items"
        # Becomes: taint_fstring_join("Hello ", name, ", you have ", count, " items")
    """
    # First collect all taint origins before unwrapping
    all_origins = set()
    for a in args:
        all_origins.update(get_taint_origins(a))

    # Unwrap all arguments and convert to strings
    unwrapped_args = [str(untaint_if_needed(a)) for a in args]
    result = "".join(unwrapped_args)

    if all_origins:
        return TaintStr(result, list(all_origins))
    return result


def taint_format_string(format_string, *args, **kwargs):
    """
    Taint-aware replacement for .format() string method calls.

    This function replaces calls to str.format() to preserve taint information
    through string formatting operations. It handles both positional and
    keyword arguments while tracking which parts of the result contain
    tainted data.

    The function:
    1. Collects taint origins from format string and all arguments
    2. Unwraps all arguments to get raw values
    3. Performs the string formatting operation
    4. Returns a TaintStr if any taint exists

    Args:
        format_string (str): The format string template
        *args: Positional arguments for formatting
        **kwargs: Keyword arguments for formatting

    Returns:
        str or TaintStr: The formatted string with taint information preserved

    Example:
        # Original: "Hello {}, you have {} items".format(name, count)
        # Becomes: taint_format_string("Hello {}, you have {} items", name, count)
    """
    # Collect taint origins before unwrapping
    all_origins = set(get_taint_origins(format_string))
    for a in args:
        all_origins.update(get_taint_origins(a))
    for v in kwargs.values():
        all_origins.update(get_taint_origins(v))

    # Unwrap all arguments before formatting
    unwrapped_format_string = untaint_if_needed(format_string)
    unwrapped_args = [untaint_if_needed(a) for a in args]
    unwrapped_kwargs = {k: untaint_if_needed(v) for k, v in kwargs.items()}

    result = unwrapped_format_string.format(*unwrapped_args, **unwrapped_kwargs)

    if all_origins:
        return TaintStr(result, list(all_origins))
    return result


def taint_percent_format(format_string, values):
    """
    Taint-aware replacement for % string formatting operations.

    This function replaces Python's % formatting operator to preserve taint
    information through printf-style string formatting. It handles both
    single values and tuples/lists of values while tracking tainted content.

    The function:
    1. Collects taint origins from format string and values
    2. Unwraps all arguments to get raw values
    3. Performs the % formatting operation
    4. Returns a TaintStr if any taint exists

    Args:
        format_string (str): The format string with % placeholders
        values: The values to format (single value, tuple, or list)

    Returns:
        str or TaintStr: The formatted string with taint information preserved

    Example:
        # Original: "Hello %s, you have %d items" % (name, count)
        # Becomes: taint_percent_format("Hello %s, you have %d items", (name, count))
    """
    # Collect taint origins before unwrapping
    all_origins = set(get_taint_origins(format_string))
    if isinstance(values, (tuple, list)):
        for v in values:
            all_origins.update(get_taint_origins(v))
    else:
        all_origins.update(get_taint_origins(values))

    # Unwrap arguments before formatting
    unwrapped_format_string = untaint_if_needed(format_string)
    unwrapped_values = untaint_if_needed(values)

    result = unwrapped_format_string % unwrapped_values

    if all_origins:
        return TaintStr(result, list(all_origins))
    return result


class TaintPropagationTransformer(ast.NodeTransformer):
    """
    Unified AST transformer that rewrites all taint-relevant operations.

    This transformer performs comprehensive AST rewriting for taint tracking by handling:

    1. String formatting operations:
       - F-strings (f"...{expr}...") -> taint_fstring_join calls
       - .format() calls ("...{}...".format(args)) -> taint_format_string calls
       - % formatting ("...%s..." % values) -> taint_percent_format calls

    2. Third-party function calls:
       - Library calls (re.search, json.dumps, etc.) -> exec_func wrapped calls
       - Only wraps functions from outside the project (third-party code)
       - Skips user-defined functions and dunder methods

    The transformer preserves the original AST structure while replacing operations
    with taint-aware equivalents that track the flow of sensitive data.

    Usage:
        transformer = TaintPropagationTransformer(module_to_file=user_modules, current_file="/path/to/file.py")
        tree = ast.parse(source_code)
        new_tree = transformer.visit(tree)
        compiled_code = compile(new_tree, filename, 'exec')
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
        Transform .format() calls and function calls with exec_func wrapping.

        Handles four types of transformations:
        1. .format() method calls -> taint_format_string calls
        2. Third-party library calls (simple or chained) -> exec_func wrapped calls
           - Simple: module.function()
           - Chained: google.genai.models.generate_content()
        3. Direct function calls (function_name()) -> exec_func wrapped calls

        Args:
            node (ast.Call): The function call AST node to potentially transform

        Returns:
            ast.Call: Either a transformed call or the original node
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

        # Check if this is an attribute access call (could be simple or chained)
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

            # Skip dunder methods - never wrap these, regardless of what they're called on
            # This is important for patterns like super().__init__() or obj.method().__getitem__()
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

            # For chained expressions (e.g., obj.method().__init__()), we need to check
            # if the base of the chain is a Call node. If it is, and the final method is a dunder,
            # we should skip wrapping the entire chain to avoid wrapping super().__init__() etc.
            # Note: The above check already handles this, but we keep this comment for clarity

            # Extract the full dotted path (e.g., "google.genai.models" from google.genai.models.generate_content)
            if isinstance(node.func.value, (ast.Attribute, ast.Name)):
                full_path, base_name = self._extract_dotted_name(node.func.value)

                if full_path is None:
                    # Couldn't extract a dotted path, skip wrapping
                    return node

                # Check if this is user code - check both the base name and full path
                if self._is_user_module(base_name) or self._is_user_module(full_path):
                    return node

            # This is a third-party call, wrap it with exec_func
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

            # Create user_py_files list to pass as 4th argument
            user_files_constant = ast.List(
                elts=[ast.Constant(value=file_path) for file_path in self.user_py_files],
                ctx=ast.Load(),
            )
            ast.copy_location(user_files_constant, node)

            new_node = ast.Call(
                func=func_node,
                args=[node.func, args_tuple, kwargs_dict, user_files_constant],
                keywords=[],
            )
            ast.copy_location(new_node, node)
            ast.fix_missing_locations(new_node)
            return new_node

        # Check if this is a direct function call (function_name())
        elif isinstance(node.func, ast.Name):
            func_name = node.func.id

            # Skip certain builtin functions that should never be wrapped
            # - super: Used in super().__init__() patterns, wrapping it breaks inheritance
            # - type, isinstance, issubclass: Type introspection functions
            # - hasattr, getattr, setattr, delattr: Attribute access functions
            builtins_to_skip = {
                "super",
                "isinstance",
                "issubclass",
                "type",
                "hasattr",
                "getattr",
                "setattr",
                "delattr",
            }
            if func_name in builtins_to_skip:
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

            # Create user_py_files list to pass as 4th argument
            user_files_constant = ast.List(
                elts=[ast.Constant(value=file_path) for file_path in self.user_py_files],
                ctx=ast.Load(),
            )
            ast.copy_location(user_files_constant, node)

            new_node = ast.Call(
                func=func_node,
                args=[node.func, args_tuple, kwargs_dict, user_files_constant],
                keywords=[],
            )
            ast.copy_location(new_node, node)
            ast.fix_missing_locations(new_node)
            return new_node

        return node

    def visit_BinOp(self, node):
        """
        Transform % formatting operations into taint_percent_format calls.

        Detects binary modulo operations where the left operand is a string
        literal and converts them to equivalent taint_percent_format calls.

        Args:
            node (ast.BinOp): The binary operation AST node to potentially transform

        Returns:
            ast.Call or ast.BinOp: Either a transformed taint_percent_format call
                                  or the original node
        """
        # First, recursively visit child nodes
        node = self.generic_visit(node)

        # Check for string % formatting
        if isinstance(node.op, ast.Mod) and (
            isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)
        ):
            # Mark that we need taint imports
            self.needs_taint_imports = True

            # Replace with taint_percent_format(format_string, values)
            new_node = ast.Call(
                func=ast.Name(id="taint_percent_format", ctx=ast.Load()),
                args=[node.left, node.right],
                keywords=[],
            )
            return ast.copy_location(new_node, node)

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

    def _is_user_module(self, module_name):
        """Check if a module name refers to user code (inside project_root)."""
        if not self.module_to_file:
            return False

        # Direct lookup: is this module name in our user modules?
        return module_name in self.module_to_file

    def _extract_dotted_name(self, node):
        """
        Extract the full dotted name from a chained attribute access.

        Examples:
            google.genai.models.generate_content -> returns "google.genai.models"
            module.Class.method -> returns "module.Class"
            simple_name -> returns "simple_name"

        Args:
            node: An AST node (could be ast.Name or ast.Attribute)

        Returns:
            A tuple of (full_dotted_path, base_name) or (None, None) if not extractable
            For example: ("google.genai.models", "google")
        """
        parts = []
        current = node

        # Walk up the chain of attributes
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value

        # Base case: we should end with an ast.Name
        if isinstance(current, ast.Name):
            parts.append(current.id)
            # Reverse to get the correct order
            parts.reverse()
            full_path = ".".join(parts)
            base_name = parts[0] if parts else None
            return full_path, base_name

        return None, None

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

        if has_future_imports:
            # Insert after the last __future__ import
            insertion_point = last_future_import_pos + 1
        else:
            # Insert at the beginning if no __future__ imports
            insertion_point = 0

        # Create safe import with fallbacks for plain Python execution
        safe_import_code = """
import os
# Fallback implementations for plain Python execution
def exec_func(func, args, kwargs, user_py_files=None):
    return func(*args, **kwargs)
def taint_fstring_join(*args):
    return "".join(str(a) for a in args)
def taint_format_string(fmt, *args, **kwargs):
    return fmt.format(*args, **kwargs)
def taint_percent_format(fmt, values):
    return fmt % values
def set_lost_taint(values):
    return
try:
    # only if we are in aco-launch mode, try to import
    if os.environ.get("AGENT_COPILOT_ENABLE_TRACING", False):
        from aco.server.ast_transformer import exec_func, taint_fstring_join, taint_format_string, taint_percent_format
        try:
            from aco.runner.monkey_patching.patching_utils import set_lost_taint
        except Exception:
            pass
except Exception:
    pass
"""

        # Parse the safe import code and inject it
        safe_import_tree = ast.parse(safe_import_code)

        # Set line numbers to 0 for injected code to hide it from debugger
        # This prevents the debugger from trying to map these lines to the original source
        for node in ast.walk(safe_import_tree):
            if hasattr(node, "lineno"):
                node.lineno = 0
            if hasattr(node, "end_lineno"):
                node.end_lineno = 0
            if hasattr(node, "col_offset"):
                node.col_offset = 0
            if hasattr(node, "end_col_offset"):
                node.end_col_offset = 0

        # Insert all nodes from the safe import at the proper insertion point
        for i, node in enumerate(safe_import_tree.body):
            tree.body.insert(insertion_point + i, node)

        return tree


def _is_user_function(func, user_py_files=None):
    """
    Determine if a function user code, including decorated user functions.

    This function handles the common case where user functions are wrapped by
    third-party decorators (like @retry, @cache, etc.) which makes getsourcefile()
    point to the decorator's source instead of the user's source.

    Detection strategies:
    1. Direct source file check (original logic)
    2. Check __wrapped__ attribute (functools.wraps standard)
    3. Recursive unwrapping for nested decorators

    Args:
        func: Function object to check
        user_py_files: List of user Python file paths

    Returns:
        bool: True if this is user code, False if third-party
    """
    if func in [reversed, enumerate, iter, map, filter, zip, range]:
        # Special case: Function that should not be wrapped, because it returns
        # an object that cannot be tainted, e.g. an iterator
        return True

    # All builtins that are not on the whitelist are not taint-wrapped
    if isbuiltin(func) and not func in [str, repr, int, float, bool, min, max, sum]:
        return False

    # there are no user files, everything is 3rd party
    if not user_py_files:
        return False

    # direct source file check (handles undecorated functions)
    try:
        source_file = getsourcefile(func)
    except TypeError:
        # Built-in function or function without source file
        return False

    if source_file and source_file in user_py_files:
        return True

    # source file not found, or source_file not in user_py_files
    # check __wrapped__ attribute (functools.wraps pattern)
    # this handles most well-behaved decorators including @retry, @lru_cache, etc.
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
    try:
        bytes_string = dumps(bound_self)
    except (PicklingError, TypeError):
        try:
            bound_hash = hash_input(bound_self)
        except Exception:
            try:
                json_str = json_dumps(bound_self)
                bound_hash = hash_input(json_str)
            except Exception:
                pass
    else:
        bound_hash = hash_input(bytes_string)
    return bound_hash


def exec_func(func, args, kwargs, user_py_files=None):
    """
    Execute an arbitrary function with taint propagation.

    This function is called by rewritten user code to propagate taint through
    arbitrary function calls. It extracts taint from all arguments, calls the
    original function with untainted arguments, and applies taint to the result.

    Args:
        func: The function object to call (e.g., re.match, json.dumps)
        args: Tuple of positional arguments
        kwargs: Dict of keyword arguments
        user_py_files: List of user Python file paths for smart detection

    Returns:
        The function result, wrapped with taint if any input was tainted

    Example:
        # Rewritten from: result = json.dumps({"key": tainted_value})
        # To: result = exec_func(json.dumps, ({"key": tainted_value},), {}, ["/path/to/user/files"])
    """
    from aco.runner.monkey_patching.patching_utils import set_lost_taint

    def _get_bound_self(f):
        """Extract the bound object from a method or partial."""
        if hasattr(f, "__self__"):
            return f.__self__
        if hasattr(f, "func") and hasattr(f.func, "__self__"):
            return f.func.__self__
        return None

    def _compute_hashes(items):
        return [_get_bound_obj_hash(el) for el in items]

    def _was_mutated(hash_before, hash_after):
        """Return True if the object was mutated (hashes differ or couldn't be computed)."""
        if hash_before is None or hash_after is None:
            return True
        return hash_before != hash_after

    def _collect_all_origins(a, kw, bound):
        """Collect taint origins from args, kwargs, and bound self."""
        origins = set()
        origins.update(get_taint_origins(a))
        origins.update(get_taint_origins(kw))
        if bound is not None:
            origins.update(get_taint_origins(bound))
        return origins

    def _retaint_mutated_args(untainted_a, untainted_kw, hashes_before, hashes_after, origins):
        """Re-taint any arguments that were mutated during the function call."""
        args_before, kwargs_before = hashes_before
        args_after, kwargs_after = hashes_after

        for arg, before, after in zip(untainted_a, args_before, args_after):
            if _was_mutated(before, after):
                taint_wrap(arg, origins, inplace=True)

        for val, before, after in zip(untainted_kw.values(), kwargs_before, kwargs_after):
            if _was_mutated(before, after):
                taint_wrap(val, origins, inplace=True)

    def _update_bound_self_taint(bound, a, kw):
        """Update a TaintObject's taint with new taint from inputs."""
        if bound is None or not hasattr(bound, "_taint_origin"):
            return

        input_taint = set(get_taint_origins(a)) | set(get_taint_origins(kw))
        if not input_taint:
            return

        try:
            current = object.__getattribute__(bound, "_taint_origin")
            object.__setattr__(bound, "_taint_origin", list(set(current) | input_taint))
        except (AttributeError, TypeError):
            pass

    def _taint_bound_self_if_mutated(bound, hash_before, hash_after, origins):
        """Taint the bound object in-place if it was mutated."""
        if bound is not None and _was_mutated(hash_before, hash_after):
            taint_wrap(bound, taint_origin=origins, inplace=True)

    if iscoroutinefunction(func):

        async def wrapper():
            if _is_user_function(func, user_py_files):
                return await func(*args, **kwargs)

            bound_self = _get_bound_self(func)
            all_origins = _collect_all_origins(args, kwargs, bound_self)

            if not all_origins:
                return await func(*args, **kwargs)

            set_lost_taint(all_origins)

            untainted_args = untaint_if_needed(args)
            untainted_kwargs = untaint_if_needed(kwargs)

            hashes_before = (
                _compute_hashes(untainted_args),
                _compute_hashes(untainted_kwargs.values()),
            )
            bound_hash_before = _get_bound_obj_hash(bound_self)

            result = await func(*untainted_args, **untainted_kwargs)

            hashes_after = (
                _compute_hashes(untainted_args),
                _compute_hashes(untainted_kwargs.values()),
            )
            bound_hash_after = _get_bound_obj_hash(bound_self)

            _retaint_mutated_args(
                untainted_args, untainted_kwargs, hashes_before, hashes_after, all_origins
            )
            set_lost_taint(set())

            _update_bound_self_taint(bound_self, args, kwargs)
            _taint_bound_self_if_mutated(
                bound_self, bound_hash_before, bound_hash_after, all_origins
            )

            return taint_wrap(result, taint_origin=all_origins)

        return wrapper()

    # Sync path
    if _is_user_function(func, user_py_files):
        return func(*args, **kwargs)

    bound_self = _get_bound_self(func)
    all_origins = _collect_all_origins(args, kwargs, bound_self)

    if not all_origins:
        return func(*args, **kwargs)

    set_lost_taint(all_origins)

    untainted_args = untaint_if_needed(args)
    untainted_kwargs = untaint_if_needed(kwargs)

    hashes_before = (_compute_hashes(untainted_args), _compute_hashes(untainted_kwargs.values()))
    bound_hash_before = _get_bound_obj_hash(bound_self)

    result = func(*untainted_args, **untainted_kwargs)

    hashes_after = (_compute_hashes(untainted_args), _compute_hashes(untainted_kwargs.values()))
    bound_hash_after = _get_bound_obj_hash(bound_self)

    _retaint_mutated_args(
        untainted_args, untainted_kwargs, hashes_before, hashes_after, all_origins
    )
    set_lost_taint(set())

    _update_bound_self_taint(bound_self, args, kwargs)
    _taint_bound_self_if_mutated(bound_self, bound_hash_before, bound_hash_after, all_origins)

    return taint_wrap(result, taint_origin=all_origins)
