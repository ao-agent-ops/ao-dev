"""
AST helper functions for taint tracking.

This module provides the core functions used by AST-rewritten code to
track data flow (taint) through program execution.

Core concepts:
- TAINT_DICT: WeakKeyDictionary storing all taint info as {obj: {"self": [origins], ...}}
- TaintWrapper: Minimal wrapper to make built-ins weak-referenceable (stores NO taint)
- ACTIVE_TAINT: ContextVar for passing taint through third-party code boundaries
"""

from inspect import getsourcefile, iscoroutinefunction
from aco.common.utils import get_aco_py_files


# =============================================================================
# Core Taint Infrastructure (Phase 1)
# =============================================================================


def wrap_if_needed(obj):
    """
    Wrap object in TaintWrapper if it doesn't support weak references.

    Does NOT handle taint - only makes objects weak-referenceable.
    """
    from aco.runner.taint_wrappers import TaintWrapper

    # Don't double-wrap
    if isinstance(obj, TaintWrapper):
        return obj

    # Don't wrap special types
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, type):
        return obj

    import inspect

    if inspect.isfunction(obj) or inspect.ismodule(obj):
        return obj

    # Check weak ref support
    try:
        import weakref

        weakref.ref(obj)
        return obj  # Supports weak refs
    except TypeError:
        return TaintWrapper(obj)  # Needs wrapping


def add_to_taint_dict_and_return(obj, taint):
    """
    Add obj to TAINT_DICT with given taint, wrapping if needed. Returns obj.

    Args:
        obj: Object to add to TAINT_DICT
        taint: List of taint origin identifiers (REQUIRED)

    Returns:
        The object (wrapped if it was a built-in that doesn't support weak refs)
    """
    import builtins

    result = wrap_if_needed(obj)
    try:
        builtins.TAINT_DICT[result] = {"self": list(taint)}
    except TypeError:
        pass  # Unhashable - can't track
    return result


def get_taint(obj):
    """
    Get taint for an object from TAINT_DICT.

    Returns [] if not found or unhashable.
    """
    import builtins

    try:
        if obj in builtins.TAINT_DICT:
            return list(builtins.TAINT_DICT[obj].get("self", []))
    except TypeError:
        pass
    return []


def untaint_if_needed(val, _seen=None):
    """
    Recursively unwrap TaintWrapper objects.

    Re-exported from taint_wrappers for convenience.
    """
    from aco.runner.taint_wrappers import untaint_if_needed as _untaint

    return _untaint(val, _seen)


def get_taint_origins(val, _seen=None):
    """
    Extract all taint origins from a value and its nested structures.

    Re-exported from taint_wrappers for convenience.
    """
    from aco.runner.taint_wrappers import get_taint_origins as _get_origins

    return _get_origins(val, _seen)


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
                all_origins.update(get_taint_origins(item))
        elif isinstance(inp, dict):
            for value in inp.values():
                all_origins.update(get_taint_origins(value))
        else:
            all_origins.update(get_taint_origins(inp))

    # Call the operation function with untainted inputs
    result = operation_func(*[untaint_if_needed(inp) for inp in inputs])

    # Return result with taint via TAINT_DICT
    return add_to_taint_dict_and_return(result, taint=list(all_origins))


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

    Unlike get_taint_origins (which returns only an object's own taint),
    this function recurses into collections to find all tainted items.
    Used internally by exec_func.
    """
    from aco.runner.taint_wrappers import TaintWrapper

    origins = set()

    def collect_from_value(val, seen=None):
        if seen is None:
            seen = set()

        obj_id = id(val)
        if obj_id in seen:
            return
        seen.add(obj_id)

        # Check for own taint
        origins.update(get_taint_origins(val))

        # Unwrap TaintWrapper to get the actual value for recursion
        actual_val = val
        if isinstance(val, TaintWrapper):
            actual_val = object.__getattribute__(val, "obj")

        # Recurse into collections
        if isinstance(actual_val, (list, tuple)):
            for item in actual_val:
                collect_from_value(item, seen)
        elif isinstance(actual_val, dict):
            for v in actual_val.values():
                collect_from_value(v, seen)
        elif isinstance(actual_val, set):
            for item in actual_val:
                collect_from_value(item, seen)

    collect_from_value(args)
    collect_from_value(kwargs)

    return origins


def _is_user_function(func):
    """
    Check if function is user code or third-party code.

    Handles decorated functions by unwrapping via __wrapped__ attribute.
    """
    from aco.common.utils import MODULES_TO_FILES

    user_py_files = list(MODULES_TO_FILES.values()) + get_aco_py_files()

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


def _is_type_annotation_access(obj, key):
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


def exec_mutation(obj, args, kwargs, method_name):
    """
    Execute mutating method directly on raw object.

    For collection mutating methods (append, extend, insert, add, update),
    we need to:
    1. Access the raw object (not a copy from untaint_if_needed)
    2. NOT untaint the args (to preserve wrapped items in collection)

    This allows mutations to work correctly and tainted items to be stored
    in collections with their TAINT_DICT entries preserved.
    """
    from aco.runner.taint_wrappers import TaintWrapper

    if isinstance(obj, TaintWrapper):
        raw_obj = object.__getattribute__(obj, "obj")
    else:
        raw_obj = obj

    func = getattr(raw_obj, method_name)
    return func(*args, **kwargs)


def exec_query(obj, args, kwargs, method_name):
    """
    Execute query method on fully unwrapped object.

    For collection query methods (count, index), we:
    1. Deeply unwrap the object (so items are raw values for comparison)
    2. Deeply unwrap the search args
    3. Return result with object's taint
    """
    from aco.runner.taint_wrappers import unwrap_deep

    obj_taint = get_taint_origins(obj)

    # Deep unwrap: object AND its contents for proper comparison
    unwrapped_obj = unwrap_deep(obj)
    unwrapped_args = unwrap_deep(args)
    unwrapped_kwargs = unwrap_deep(kwargs)

    func = getattr(unwrapped_obj, method_name)
    result = func(*unwrapped_args, **unwrapped_kwargs)

    if obj_taint:
        return add_to_taint_dict_and_return(result, taint=obj_taint)
    return result


def exec_inplace(obj, args, kwargs, method_name):
    """
    Execute in-place modification on raw object with unwrapped args.

    For collection in-place methods (remove, sort, reverse, pop, clear), we:
    1. Access the raw object (flat unwrap to preserve the original container)
    2. Deeply unwrap args (so remove("x") finds items correctly)
    3. For remove: unwrap items in-place before the operation
    4. Execute the method (modifies collection in place)
    5. Return result with object's taint if applicable
    """
    from aco.runner.taint_wrappers import TaintWrapper, unwrap_flat, unwrap_deep

    obj_taint = get_taint_origins(obj)

    # Flat unwrap to get the actual container (not a copy)
    raw_obj = unwrap_flat(obj)

    # For methods that compare items (remove), unwrap items in-place first
    if method_name == "remove" and isinstance(raw_obj, list):
        for i, item in enumerate(raw_obj):
            if isinstance(item, TaintWrapper):
                raw_obj[i] = object.__getattribute__(item, "obj")

    unwrapped_args = unwrap_deep(args)
    unwrapped_kwargs = unwrap_deep(kwargs)

    func = getattr(raw_obj, method_name)
    result = func(*unwrapped_args, **unwrapped_kwargs)

    # For methods that return values (pop), preserve item's taint or inherit from parent
    if result is not None:
        result_taint = get_taint_origins(result)
        if result_taint:
            return result  # Item has its own taint, keep it
        elif obj_taint:
            return add_to_taint_dict_and_return(result, taint=obj_taint)
    return result


def exec_setitem(obj, key, value):
    """
    Execute setitem directly on raw object, preserving tainted values.

    For l[key] = value, we:
    1. Get raw container (flat unwrap, don't recursively unwrap contents)
    2. Unwrap key for proper indexing
    3. DON'T unwrap value - store as-is to preserve TaintWrapper items
    """
    from aco.runner.taint_wrappers import unwrap_flat, unwrap_deep

    raw_obj = unwrap_flat(obj)
    unwrapped_key = unwrap_deep(key)
    # Store value as-is to preserve TaintWrapper items in the collection
    raw_obj[unwrapped_key] = value
    return None


def exec_delitem(obj, key):
    """
    Execute delitem directly on raw object.

    For del l[key], we:
    1. Get raw container (flat unwrap)
    2. Unwrap key for proper indexing
    3. Delete the item
    """
    from aco.runner.taint_wrappers import unwrap_flat, unwrap_deep

    raw_obj = unwrap_flat(obj)
    unwrapped_key = unwrap_deep(key)
    del raw_obj[unwrapped_key]
    return None


def exec_inplace_binop(obj, value, op_name):
    """
    Execute in-place binary operation on object.

    For l += x or l *= n, we:
    1. Get raw container (flat unwrap to preserve TAINT_DICT entry)
    2. Execute in-place operation on raw object
    3. Return original wrapper (not raw result) to preserve TAINT_DICT reference
    """
    import operator
    from aco.runner.taint_wrappers import TaintWrapper, unwrap_flat, unwrap_deep

    raw_obj = unwrap_flat(obj)
    op_func = getattr(operator, op_name)

    # For list iadd, don't unwrap value items so tainted items are preserved
    if op_name == "iadd" and isinstance(raw_obj, list):
        op_func(raw_obj, value)
    elif op_name == "imul" and isinstance(raw_obj, list):
        unwrapped_value = unwrap_deep(value)
        op_func(raw_obj, unwrapped_value)
    else:
        unwrapped_value = unwrap_deep(value)
        op_func(raw_obj, unwrapped_value)

    # Return the original wrapper to preserve TAINT_DICT entry
    if isinstance(obj, TaintWrapper):
        return obj
    return raw_obj


def exec_func(func_or_obj, args, kwargs, method_name=None):
    """
    Execute function with taint tracking.

    For method calls: pass (obj, args, kwargs, method_name="method")
    For standalone functions: pass (func, args, kwargs)

    User code: called directly with wrapped args
    Third-party code: arguments untainted, ACTIVE_TAINT set, results tainted
    """
    # Resolve the actual function and collect object taint
    if method_name is not None:
        # Method call: func_or_obj is the object
        from aco.runner.taint_wrappers import unwrap_flat

        obj = func_or_obj
        obj_taint = get_taint_origins(obj)
        unwrapped_obj = unwrap_flat(obj)
        func = getattr(unwrapped_obj, method_name)
    else:
        # Standalone function or already-bound method
        obj = None
        obj_taint = []
        func = func_or_obj
        # Check if it's a bound method
        if hasattr(func, "__self__"):
            obj_taint = get_taint_origins(func.__self__)

    if iscoroutinefunction(func):
        return _exec_async_wrapper(func, args, kwargs, obj_taint)

    # User code: call directly
    if _is_user_function(func):
        try:
            return func(*args, **kwargs)
        except Exception:
            pass  # Fall through to third-party handling

    return _exec_third_party_sync(func, args, kwargs, obj_taint)


def _exec_async_wrapper(func, args, kwargs, obj_taint=None):
    """Create async wrapper for coroutine functions."""
    if obj_taint is None:
        obj_taint = []

    async def wrapper():
        if _is_user_function(func):
            try:
                return await func(*args, **kwargs)
            except Exception:
                pass

        return await _exec_third_party_async(func, args, kwargs, obj_taint)

    return wrapper()


def _exec_third_party_sync(func, args, kwargs, obj_taint=None):
    """Execute third-party sync function with taint tracking."""
    import builtins

    if obj_taint is None:
        obj_taint = []

    # Collect taint from all inputs (recursively from args/kwargs)
    all_origins = set(obj_taint)
    all_origins.update(_collect_taint_from_args(args, kwargs))

    taint = list(all_origins)

    # Set ACTIVE_TAINT for monkey-patched code
    builtins.ACTIVE_TAINT.set(taint)

    try:
        # Untaint arguments
        untainted_args = untaint_if_needed(args)
        untainted_kwargs = untaint_if_needed(kwargs)

        # Handle type annotations specially
        if hasattr(func, "__name__") and func.__name__ == "getitem" and len(untainted_args) >= 2:
            obj, key = untainted_args[0], untainted_args[1]
            if _is_type_annotation_access(obj, key):
                return func(*untainted_args, **untainted_kwargs)

        # Call function
        result = func(*untainted_args, **untainted_kwargs)

        # Check if result is a coroutine (sync func returning coroutine)
        import asyncio

        if asyncio.iscoroutine(result):
            return _wrap_coroutine_with_taint(result, taint)

        # Wrap result with collected taint
        final_taint = list(builtins.ACTIVE_TAINT.get())
        return add_to_taint_dict_and_return(result, taint=final_taint)

    finally:
        builtins.ACTIVE_TAINT.set([])


async def _exec_third_party_async(func, args, kwargs, obj_taint=None):
    """Execute third-party async function with taint tracking."""
    import builtins

    if obj_taint is None:
        obj_taint = []

    # Collect taint from all inputs (recursively from args/kwargs)
    all_origins = set(obj_taint)
    all_origins.update(_collect_taint_from_args(args, kwargs))

    taint = list(all_origins)

    builtins.ACTIVE_TAINT.set(taint)

    try:
        untainted_args = untaint_if_needed(args)
        untainted_kwargs = untaint_if_needed(kwargs)

        result = await func(*untainted_args, **untainted_kwargs)

        final_taint = list(builtins.ACTIVE_TAINT.get())
        return add_to_taint_dict_and_return(result, taint=final_taint)

    finally:
        builtins.ACTIVE_TAINT.set([])


async def _wrap_coroutine_with_taint(coro, taint):
    """Wrap coroutine to set taint context when awaited."""
    import builtins

    builtins.ACTIVE_TAINT.set(taint)
    try:
        result = await coro
        final_taint = list(builtins.ACTIVE_TAINT.get())
        return add_to_taint_dict_and_return(result, taint=final_taint)
    finally:
        builtins.ACTIVE_TAINT.set([])


# =============================================================================
# Assignment and Access Interception
# =============================================================================


def intercept_assign(op_type, obj_or_name, attr_or_none, value):
    """
    Unified assignment interceptor for taint tracking.

    Args:
        op_type: 'name', 'attr', or 'subscript'
        obj_or_name: Target object (for attr/subscript) or variable name (for name)
        attr_or_none: Attribute name (for attr), key (for subscript), or None (for name)
        value: Value being assigned

    Returns:
        The assigned value (potentially wrapped for primitives)
    """
    import builtins

    # Get taint origins from the value being assigned
    taint_origins = get_taint_origins(value)

    if op_type == "name":
        # Variable assignment: a = value
        return add_to_taint_dict_and_return(value, taint=taint_origins)

    elif op_type == "attr":
        # Attribute assignment: obj.attr = value
        try:
            if taint_origins and obj_or_name is not None:
                try:
                    # Ensure parent is in TAINT_DICT
                    if obj_or_name not in builtins.TAINT_DICT:
                        add_to_taint_dict_and_return(obj_or_name, taint=[])

                    # Check if value supports weak refs
                    import weakref

                    unwrapped_value = untaint_if_needed(value)
                    try:
                        weakref.ref(unwrapped_value)
                        # Value supports weak refs - give it its own entry
                        add_to_taint_dict_and_return(unwrapped_value, taint=taint_origins)
                        # Remove from parent's shadow if present
                        if attr_or_none in builtins.TAINT_DICT[obj_or_name]:
                            del builtins.TAINT_DICT[obj_or_name][attr_or_none]
                    except TypeError:
                        # Value is a built-in - store in parent's shadow
                        builtins.TAINT_DICT[obj_or_name][attr_or_none] = list(taint_origins)
                except TypeError:
                    pass

            # Perform actual assignment
            unwrapped_value = untaint_if_needed(value)
            setattr(obj_or_name, attr_or_none, unwrapped_value)

        except Exception:
            # Fall back to normal assignment
            unwrapped_value = untaint_if_needed(value)
            setattr(obj_or_name, attr_or_none, unwrapped_value)

        return value

    elif op_type == "subscript":
        try:
            if taint_origins and obj_or_name is not None:
                try:
                    if obj_or_name not in builtins.TAINT_DICT:
                        add_to_taint_dict_and_return(obj_or_name, taint=[])
                    # Store subscript taint in parent's shadow
                    key_str = str(attr_or_none)
                    builtins.TAINT_DICT[obj_or_name][key_str] = list(taint_origins)
                except TypeError:
                    pass

            # Perform actual assignment
            unwrapped_value = untaint_if_needed(value)
            unwrapped_key = untaint_if_needed(attr_or_none)
            obj_or_name[unwrapped_key] = unwrapped_value

        except Exception:
            unwrapped_value = untaint_if_needed(value)
            unwrapped_key = untaint_if_needed(attr_or_none)
            obj_or_name[unwrapped_key] = unwrapped_value

        return value

    return value


def intercept_access(op_type, obj_or_name, attr_or_none):
    """
    Unified access interceptor for taint tracking.

    Args:
        op_type: 'name', 'attr', or 'subscript'
        obj_or_name: Source object (for attr/subscript) or variable name (for name)
        attr_or_none: Attribute name (for attr), key (for subscript), or None (for name)

    Returns:
        The accessed value with taint propagation
    """
    import builtins

    if op_type == "name":
        # Variable access: x
        import inspect

        frame = inspect.currentframe().f_back.f_back

        if obj_or_name in frame.f_locals:
            return frame.f_locals[obj_or_name]
        elif obj_or_name in frame.f_globals:
            return frame.f_globals[obj_or_name]
        else:
            raise NameError(f"name '{obj_or_name}' is not defined")

    elif op_type == "attr":
        # Attribute access: obj.attr
        from aco.runner.taint_wrappers import unwrap_flat

        unwrapped_parent = unwrap_flat(obj_or_name)
        result = getattr(unwrapped_parent, attr_or_none)

        # Resolve taint
        try:
            shadow = builtins.TAINT_DICT.get(obj_or_name, {})
            if attr_or_none in shadow:
                # Built-in attribute - taint stored in parent's shadow
                taint = shadow[attr_or_none]
            elif result in builtins.TAINT_DICT:
                # Object attribute - has own TAINT_DICT entry
                taint = builtins.TAINT_DICT[result].get("self", [])
            else:
                # Fallback to parent's taint
                taint = shadow.get("self", [])
        except TypeError:
            taint = []

        return add_to_taint_dict_and_return(result, taint=list(taint))

    elif op_type == "subscript":
        # Subscript access: obj[key]
        from aco.runner.taint_wrappers import TaintWrapper

        if isinstance(obj_or_name, TaintWrapper):
            raw_parent = object.__getattribute__(obj_or_name, "obj")
        else:
            raw_parent = obj_or_name
        unwrapped_key = untaint_if_needed(attr_or_none)

        # Get item from parent
        result = raw_parent[unwrapped_key]

        # Check if item already has its own taint (TaintWrapper or TAINT_DICT)
        item_taint = get_taint_origins(result)
        if item_taint:
            return result

        # Item doesn't have its own taint - inherit parent's taint
        parent_taint = get_taint_origins(obj_or_name)
        return add_to_taint_dict_and_return(result, taint=parent_taint)

    return None


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
