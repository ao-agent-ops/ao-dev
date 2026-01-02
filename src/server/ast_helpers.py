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


def _de_intern(obj, _seen=None):
    """
    Create a copy of obj with all strings de-interned (unique ids).

    Python interns short strings, meaning different occurrences of "hello"
    may share the same id. This causes issues with id-based taint tracking
    because tainting one "hello" would taint all of them.

    The bytes encode/decode roundtrip creates a new string object with a
    unique id, solving this problem.

    Objects already in TAINT_DICT are preserved as-is since they already
    have unique ids from a previous de-interning.

    Args:
        obj: Object to de-intern (recursively for containers)
        _seen: Set of already-processed object ids (for cycle detection)

    Returns:
        Object with all strings de-interned (or original if already tainted)
    """
    if _seen is None:
        _seen = set()

    obj_id = id(obj)
    if obj_id in _seen:
        return obj  # Avoid infinite recursion on cycles

    # If object is already in TAINT_DICT, it's already de-interned.
    # Preserve it to maintain taint tracking.
    if builtins.TAINT_DICT.has_taint(obj):
        return obj

    if isinstance(obj, str):
        return obj.encode("utf-8").decode("utf-8")
    elif isinstance(obj, dict):
        _seen.add(obj_id)
        return {_de_intern(k, _seen): _de_intern(v, _seen) for k, v in obj.items()}
    elif isinstance(obj, list):
        _seen.add(obj_id)
        return [_de_intern(item, _seen) for item in obj]
    elif isinstance(obj, tuple):
        _seen.add(obj_id)
        return tuple(_de_intern(item, _seen) for item in obj)

    return obj


def add_to_taint_dict_and_return(obj, taint):
    """
    Add obj to TAINT_DICT with given taint.

    When taint is being added, strings are de-interned to ensure unique ids.
    This prevents interned strings (like "type", "user") from causing spurious
    taint propagation across unrelated code.

    If the object is already in TAINT_DICT (already de-interned), we skip
    de-interning to preserve its identity and avoid orphaning the entry.

    Args:
        obj: Object to add to TAINT_DICT
        taint: List of taint origin identifiers

    Returns:
        The object (de-interned if newly tainted)
    """
    # Skip non-taintable types
    if isinstance(obj, bool) or obj is None or isinstance(obj, type):
        return obj

    if taint:
        # Only de-intern if object is not already in TAINT_DICT.
        # This prevents double de-interning (e.g., when taint_assign is called
        # on an already-tainted object from exec_func).
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
    args_taint = _collect_taint_from_args(args, kwargs)
    all_origins.update(args_taint)
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
    # Skip non-taintable types (singletons that can't have unique ids)
    if isinstance(result, bool) or result is None or isinstance(result, type):
        return result

    # Check if result already has its own taint - preserve it as-is
    # This handles cases like pop() returning an item with its own taint
    existing_taint = get_taint(result)
    if existing_taint:
        return result

    # Get taint from ACTIVE_TAINT (accumulated from function inputs)
    active_taint = list(builtins.ACTIVE_TAINT.get())

    if active_taint:
        # De-intern result once to ensure all strings have unique ids.
        # This is done here (not in add_to_taint_dict_and_return) to avoid
        # double de-interning when we taint both items and the container.
        result = _de_intern(result)

        # Taint container items for for-loops (Python's GET_ITER/FOR_ITER
        # bytecode doesn't go through exec_func, so items need taint).
        if isinstance(result, (tuple, list)):
            for item in result:
                if not isinstance(item, bool) and item is not None:
                    if not get_taint(item):
                        builtins.TAINT_DICT.add(item, list(active_taint))

        # Taint the result itself
        builtins.TAINT_DICT.add(result, list(active_taint))
        return result

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

    # Inherit parent's taint. Items inside result (if it's a container)
    # get tainted lazily when accessed via get_item or iteration.
    parent_taint = get_taint(obj)
    return add_to_taint_dict_and_return(result, parent_taint)


def get_item(obj, key):
    """Get obj[key] with taint propagation."""
    result = obj[key]

    # If item already has taint, preserve it
    item_taint = get_taint(result)
    if item_taint:
        return result

    # Inherit parent's taint. Items inside result (if it's a container)
    # get tainted lazily when accessed via get_item or iteration.
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
