"""
AST helper functions for taint tracking.

This module provides the core functions used by AST-rewritten code to
track data flow (taint) through program execution.

Core concepts:
- TAINT_DICT: id-based dict storing {id(obj): (obj, [origins])}
- ACTIVE_TAINT: ContextVar for passing taint through third-party code boundaries

No wrappers are used. Objects are stored directly in TAINT_DICT by their id.
"""

from inspect import getsourcefile, iscoroutinefunction
import builtins


# =============================================================================
# Core Taint Infrastructure
# =============================================================================


def add_to_taint_dict_and_return(obj, taint):
    """
    Add obj to TAINT_DICT with given taint. Returns obj unchanged.

    Args:
        obj: Object to add to TAINT_DICT
        taint: List of taint origin identifiers

    Returns:
        The object unchanged (no wrapping)
    """

    # Skip non-taintable types
    if isinstance(obj, bool) or obj is None or isinstance(obj, type):
        return obj

    if taint:
        builtins.TAINT_DICT.add(obj, taint)
    return obj


def get_taint(obj):
    """
    Get taint for an object from TAINT_DICT.

    Returns [] if not found.
    """
    return builtins.TAINT_DICT.get_taint(obj)


def get_taint_origins(val, _seen=None):
    """Get taint origins for an object. Alias for get_taint."""
    return get_taint(val)


def untaint_if_needed(val, _seen=None):
    """No-op - objects are no longer wrapped."""
    return val


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
        origins.update(get_taint(val))

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
    from ao.common.utils import MODULES_TO_FILES, get_ao_py_files

    user_py_files = list(MODULES_TO_FILES.values()) + get_ao_py_files()

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


# Methods that store values - don't unwrap args to preserve taint on stored items
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
    """Execute in-place operation (+=, *=, etc.)."""
    import operator

    op_func = getattr(operator, op_name)
    result = op_func(obj, value)
    return result


def exec_func(func_or_obj, args, kwargs, method_name=None):
    """
    Execute function or method with taint tracking.

    For method calls: pass (obj, args, kwargs, method_name="method")
    For standalone functions: pass (func, args, kwargs)

    Call directly (keep args as-is) when:
    - User code: already AST-rewritten to handle taint
    - Storing methods: need to preserve taint on items being stored

    Otherwise track taint through ACTIVE_TAINT.
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

    # Third-party: track taint through ACTIVE_TAINT
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
    all_origins.update(_collect_taint_from_args(args, kwargs))
    taint = list(all_origins)

    if is_async:

        async def async_call():
            builtins.ACTIVE_TAINT.set(taint)
            try:
                result = await func(*args, **kwargs)
                return _finalize_taint(result)
            finally:
                builtins.ACTIVE_TAINT.set([])

        return async_call()
    else:
        builtins.ACTIVE_TAINT.set(taint)
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
            builtins.ACTIVE_TAINT.set([])


def _finalize_taint(result):
    """Add taint to result from ACTIVE_TAINT.

    Also propagates taint to container elements (tuples, lists) so that
    unpacking works correctly (e.g., `before, sep, after = s.partition(',')`).

    If the result already has taint (e.g., an item popped from a list that
    had its own taint), we preserve that existing taint rather than merging
    with the container's taint. This ensures items maintain their identity.
    """
    # Check if result already has its own taint - preserve it as-is
    # This handles cases like pop() returning an item with its own taint
    if get_taint(result):
        return result

    # Get taint from ACTIVE_TAINT (accumulated from function inputs)
    active_taint = list(builtins.ACTIVE_TAINT.get())

    if active_taint:
        # Propagate taint to container elements so unpacking works
        # e.g., `before, sep, after = s.partition(',')` needs each element tainted
        # But only if the element doesn't already have its own taint
        if isinstance(result, (tuple, list)):
            for item in result:
                # Skip non-taintable types
                if isinstance(item, bool) or item is None or isinstance(item, type):
                    continue
                # Only add taint if item doesn't already have its own taint
                if not get_taint(item):
                    add_to_taint_dict_and_return(item, taint=active_taint)
        return add_to_taint_dict_and_return(result, taint=active_taint)
    return result


async def _wrap_coroutine_with_taint(coro, taint):
    """Wrap coroutine to set taint context when awaited."""
    builtins.ACTIVE_TAINT.set(taint)
    try:
        result = await coro
        return _finalize_taint(result)
    finally:
        builtins.ACTIVE_TAINT.set([])


# =============================================================================
# Assignment and Access Interception
# =============================================================================


def taint_assign(value):
    """Wrap value for variable assignment (x = value).

    This function preserves any existing taint on the value.
    """
    existing_taint = get_taint(value)
    return add_to_taint_dict_and_return(value, taint=existing_taint)


def get_attr(obj, attr):
    """Get obj.attr with taint propagation."""
    result = getattr(obj, attr)

    # Use result's own taint or inherit from parent
    result_taint = get_taint(result)
    if result_taint:
        return result

    parent_taint = get_taint(obj)
    return add_to_taint_dict_and_return(result, parent_taint)


def get_item(obj, key):
    """Get obj[key] with taint propagation."""
    result = obj[key]

    # If item already has taint, preserve it
    item_taint = get_taint(result)
    if item_taint:
        return result

    # Otherwise inherit parent's taint
    parent_taint = get_taint(obj)
    return add_to_taint_dict_and_return(result, parent_taint)


def set_attr(obj, attr, value):
    """Set obj.attr = value with taint tracking."""
    setattr(obj, attr, value)
    return value


# =============================================================================
# Legacy Compatibility
# =============================================================================


def taint(obj, taint_origins):
    """
    Apply taint to an object via TAINT_DICT.

    Legacy function - new code should use add_to_taint_dict_and_return.
    """
    if not taint_origins:
        return obj
    return add_to_taint_dict_and_return(obj, taint=list(taint_origins))


def taint_wrap(obj, taint_origin=None, root_wrapper=None):
    """Add taint to object via TAINT_DICT."""
    if taint_origin is None:
        taint_origin = []
    elif isinstance(taint_origin, (int, str)):
        taint_origin = [taint_origin]

    return add_to_taint_dict_and_return(obj, taint=list(taint_origin))
