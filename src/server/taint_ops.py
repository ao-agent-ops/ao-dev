"""
AST helper functions for taint tracking.

This module provides the core functions used by AST-rewritten code to
track data flow (taint) through program execution.

Core concepts:
- TAINT_DICT: id-based dict storing {id(obj): (obj, [origins])}
- TAINT_STACK: Stack-based context for passing taint through third-party code boundaries
"""

from inspect import getsourcefile, iscoroutinefunction
import builtins


# =============================================================================
# Core Taint Infrastructure
# =============================================================================


def _is_taintable(obj):
    """Check if obj can be tainted (not a singleton type)."""
    return not isinstance(obj, bool) and obj is not None and not isinstance(obj, type)


def _de_intern_string(s):
    """Create a copy of string s with a unique id (not interned)."""
    return s.encode("utf-8").decode("utf-8")


def _de_intern(obj, _seen=None):
    """
    Create a copy of obj with all strings de-interned (unique ids).

    Python interns short strings, so different occurrences of "hello" may
    share the same id. This breaks id-based taint tracking. De-interning
    creates new string objects with unique ids. Handles cycles correctly.
    """
    if _seen is None:
        _seen = {}  # Maps old object id -> new object

    obj_id = id(obj)
    if obj_id in _seen:
        return _seen[obj_id]  # Return the NEW object for cycles

    # If object is already in TAINT_DICT, it's already de-interned.
    if builtins.TAINT_DICT.has_taint(obj):
        return obj

    if isinstance(obj, str):
        return _de_intern_string(obj)
    elif isinstance(obj, dict):
        # Pre-create empty dict and register BEFORE recursing
        new_dict = {}
        _seen[obj_id] = new_dict
        for k, v in obj.items():
            new_dict[_de_intern(k, _seen)] = _de_intern(v, _seen)
        return new_dict
    elif isinstance(obj, list):
        # Pre-create empty list and register BEFORE recursing
        new_list = []
        _seen[obj_id] = new_list
        for item in obj:
            new_list.append(_de_intern(item, _seen))
        return new_list
    elif isinstance(obj, tuple):
        # Tuples are immutable so we can't pre-create. Register original
        # so cycles back to this tuple return the original (acceptable
        # since tuples rarely form cycle roots due to immutability).
        _seen[obj_id] = obj
        return tuple(_de_intern(item, _seen) for item in obj)

    return obj


def _register_taint(obj, taint):
    """
    Low-level: Register obj in TAINT_DICT with given taint.

    Assumes obj is already de-interned. Does not de-intern.
    Used by _finalize_taint after bulk de-interning a container.
    """
    if _is_taintable(obj) and taint and not get_taint(obj):
        builtins.TAINT_DICT.add(obj, taint)


def add_to_taint_dict_and_return(obj, taint):
    """
    Add obj to TAINT_DICT with given taint, de-interning if needed.

    This is the main entry point for adding taint to objects.
    De-interns strings to ensure unique ids for id-based tracking.

    Returns the (possibly de-interned) object.
    """
    if not _is_taintable(obj):
        return obj

    if taint:
        # Only de-intern if not already in TAINT_DICT
        if not builtins.TAINT_DICT.has_taint(obj):
            obj = _de_intern(obj)
        builtins.TAINT_DICT.add(obj, taint)
    return obj


def get_taint(obj):
    """
    Get taint for an object from TAINT_DICT.

    Returns [] if not found.
    """
    return builtins.TAINT_DICT.get_taint(obj)


# =============================================================================
# String Operations
# =============================================================================


def _unified_taint_string_operation(operation_func, *inputs):
    """
    Unified helper for all taint-aware string operations.

    Args:
        operation_func: Function that performs the string operation
        *inputs: All inputs that may contain taint

    Returns:
        Result with taint information preserved
    """
    # Collect taint origins from all inputs
    all_origins = set()
    for inp in inputs:
        if isinstance(inp, (tuple, list)):
            for item in inp:
                all_origins.update(get_taint(item))
        elif isinstance(inp, dict):
            for value in inp.values():
                all_origins.update(get_taint(value))
        else:
            all_origins.update(get_taint(inp))

    # Call the operation function directly (no untainting needed)
    result = operation_func(*inputs)

    # Return result with taint via TAINT_DICT
    return add_to_taint_dict_and_return(result, taint=list(all_origins))


def taint_fstring_join(*args):
    """Taint-aware replacement for f-string concatenation."""

    def join_operation(*op_args):
        return "".join(str(arg) for arg in op_args)

    return _unified_taint_string_operation(join_operation, *args)


def taint_format_string(format_string, *args, **kwargs):
    """Taint-aware replacement for .format() string method calls."""

    def format_operation(fmt, fmt_args, fmt_kwargs):
        return fmt.format(*fmt_args, **fmt_kwargs)

    return _unified_taint_string_operation(format_operation, format_string, args, kwargs)


def taint_percent_format(format_string, values):
    """Taint-aware replacement for % string formatting operations."""

    def percent_operation(fmt, vals):
        return fmt % vals

    return _unified_taint_string_operation(percent_operation, format_string, values)


def taint_open(*args, **kwargs):
    """Taint-aware replacement for open() with database persistence."""
    # Extract filename for default taint origin
    if args and len(args) >= 1:
        filename = args[0]
    else:
        filename = kwargs.get("file") or kwargs.get("filename")

    # Call the original open
    file_obj = open(*args, **kwargs)

    # Create default taint origin from filename
    default_taint = f"file:{filename}" if filename else "file:unknown"

    # Add to TAINT_DICT with file taint
    return add_to_taint_dict_and_return(file_obj, taint=[default_taint])


# =============================================================================
# User Code Detection
# =============================================================================


def _collect_taint_from_args(args, kwargs):
    """
    Recursively collect taint origins from function arguments.

    Recurses into collections to find all tainted items.
    """
    origins = set()

    def collect_from_value(val, seen=None):
        if seen is None:
            seen = set()

        obj_id = id(val)
        if obj_id in seen:
            return
        seen.add(obj_id)

        # Check for own taint
        val_taint = get_taint(val)
        origins.update(val_taint)

        # Recurse into collections
        if isinstance(val, (list, tuple)):
            for item in val:
                collect_from_value(item, seen)
        elif isinstance(val, dict):
            for v in val.values():
                collect_from_value(v, seen)
        elif isinstance(val, set):
            for item in val:
                collect_from_value(item, seen)

    collect_from_value(args)
    collect_from_value(kwargs)

    return origins


def _is_user_function(func):
    """
    Check if function is user code or third-party code.

    Handles decorated functions by unwrapping via __wrapped__ attribute.
    """
    from ao.runner.ast_rewrite_hook import get_user_module_files
    from ao.common.utils import get_ao_py_files

    user_py_files = get_user_module_files() + get_ao_py_files()

    if not user_py_files:
        return False

    # Strategy 1: Direct source file check
    try:
        source_file = getsourcefile(func)
    except TypeError:
        return False

    if source_file and source_file in user_py_files:
        return True

    # Strategy 2: Check __wrapped__ attribute (functools.wraps pattern)
    current_func = func
    max_unwrap_depth = 10
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


def _is_type_annotation_access(obj, _key):
    """
    Detect if this is a type annotation rather than runtime access.
    """
    if isinstance(obj, type):
        return True
    if hasattr(obj, "__module__") and obj.__module__ == "typing":
        return True
    if hasattr(obj, "__origin__"):
        return True
    if hasattr(obj, "__class_getitem__"):
        obj_type_name = type(obj).__name__
        if obj_type_name in {"dict", "list", "tuple", "set"}:
            return False
        return True
    if hasattr(obj, "__name__"):
        type_names = {"Dict", "List", "Tuple", "Set", "Optional", "Union", "Any", "Callable"}
        if obj.__name__ in type_names:
            return True
    return False


# =============================================================================
# Function Execution with Taint Tracking
# =============================================================================


# Methods that store values - call directly so stored items retain their id in TAINT_DICT
STORING_METHODS = {"append", "extend", "insert", "add", "update", "setdefault"}


def exec_setitem(obj, key, value):
    """Execute obj[key] = value."""
    obj[key] = value
    return None


def exec_delitem(obj, key):
    """Execute del obj[key]."""
    del obj[key]
    return None


def exec_inplace_binop(obj, value, op_name):
    """Execute in-place operation (+=, *=, etc.) with taint propagation."""
    import operator

    # Collect taint from both operands
    all_origins = set()
    all_origins.update(get_taint(obj))
    all_origins.update(get_taint(value))

    op_func = getattr(operator, op_name)
    result = op_func(obj, value)

    # Propagate combined taint to result
    return add_to_taint_dict_and_return(result, list(all_origins))


def exec_func(func_or_obj, args, kwargs, method_name=None):
    """
    Execute function or method with taint tracking.

    For method calls: pass (obj, args, kwargs, method_name="method")
    For standalone functions: pass (func, args, kwargs)

    Call directly (keep args as-is) when:
    - User code: already AST-rewritten to handle taint
    - Storing methods: need to preserve taint on items being stored

    Otherwise track taint through TAINT_STACK.
    """

    # Resolve the actual function and collect object taint
    if method_name is not None:
        obj = func_or_obj
        obj_taint = get_taint(obj)
        func = getattr(obj, method_name)
    else:
        obj = None
        obj_taint = []
        func = func_or_obj
        if hasattr(func, "__self__"):
            obj_taint = get_taint(func.__self__)

    # Call directly if user code or storing method
    is_storing = method_name is not None and method_name in STORING_METHODS
    if _is_user_function(func) or is_storing:
        if iscoroutinefunction(func):

            async def wrapper():
                return await func(*args, **kwargs)

            return wrapper()
        return func(*args, **kwargs)

    # Third-party: track taint through TAINT_STACK
    if iscoroutinefunction(func):
        return _exec_third_party(func, args, kwargs, obj_taint, is_async=True)
    return _exec_third_party(func, args, kwargs, obj_taint, is_async=False)


def _exec_third_party(func, args, kwargs, obj_taint, is_async):
    """
    Execute third-party function with taint tracking.

    For async functions, returns a coroutine. For sync functions, returns the result.
    """
    # Collect taint from all inputs
    all_origins = set(obj_taint or [])
    args_taint = _collect_taint_from_args(args, kwargs)
    all_origins.update(args_taint)
    taint = list(all_origins)

    if is_async:

        async def async_call():
            builtins.TAINT_STACK.push(taint)
            try:
                result = await func(*args, **kwargs)
                return _finalize_taint(result)
            finally:
                builtins.TAINT_STACK.pop()

        return async_call()
    else:
        builtins.TAINT_STACK.push(taint)
        try:
            # Handle type annotations specially
            if hasattr(func, "__name__") and func.__name__ == "getitem" and len(args) >= 2:
                obj, key = args[0], args[1]
                if _is_type_annotation_access(obj, key):
                    return func(*args, **kwargs)

            result = func(*args, **kwargs)

            # Check if sync func returned a coroutine
            import asyncio

            if asyncio.iscoroutine(result):
                return _wrap_coroutine_with_taint(result, taint)

            return _finalize_taint(result)
        finally:
            builtins.TAINT_STACK.pop()


def _finalize_taint(result):
    """
    Add taint from TAINT_STACK to third-party function result.

    Also propagates taint to container elements so unpacking works
    correctly (e.g., `before, sep, after = s.partition(',')`).
    """
    if not _is_taintable(result):
        return result

    # Preserve existing taint (e.g., item popped from a tainted list)
    if get_taint(result):
        return result

    active_taint = builtins.TAINT_STACK.read()
    if not active_taint:
        return result

    # De-intern once for entire result (including nested items)
    result = _de_intern(result)

    # Register container items for for-loop iteration support
    # (Python's GET_ITER/FOR_ITER bytecode doesn't go through exec_func)
    if isinstance(result, (tuple, list)):
        for item in result:
            _register_taint(item, list(active_taint))

    # Register the container itself
    _register_taint(result, list(active_taint))

    return result


async def _wrap_coroutine_with_taint(coro, taint):
    """Wrap coroutine to set taint context when awaited."""
    builtins.TAINT_STACK.push(taint)
    try:
        result = await coro
        return _finalize_taint(result)
    finally:
        builtins.TAINT_STACK.pop()


# =============================================================================
# Assignment and Access Interception
# =============================================================================


def taint_assign(value):
    """Wrap value for variable assignment (x = value)."""
    existing_taint = get_taint(value)
    return add_to_taint_dict_and_return(value, taint=existing_taint)


def get_attr(obj, attr):
    """Get obj.attr with taint propagation."""
    result = getattr(obj, attr)

    # If result has its own taint, preserve it
    result_taint = get_taint(result)
    if result_taint:
        return result

    # De-intern strings to get unique id for taint tracking
    if isinstance(result, str):
        result = _de_intern_string(result)

    # Inherit parent's taint
    parent_taint = get_taint(obj)
    return add_to_taint_dict_and_return(result, parent_taint)


def get_item(obj, key):
    """Get obj[key] with taint propagation."""
    result = obj[key]

    # If item has its own taint, preserve it
    item_taint = get_taint(result)
    if item_taint:
        return result

    # De-intern strings to get unique id for taint tracking
    if isinstance(result, str):
        result = _de_intern_string(result)

    # Inherit parent's taint
    parent_taint = get_taint(obj)
    return add_to_taint_dict_and_return(result, parent_taint)


def set_attr(obj, attr, value):
    """Set obj.attr = value with taint tracking."""
    setattr(obj, attr, value)
    return value
