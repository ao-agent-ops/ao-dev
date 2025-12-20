"""
Minimal wrapper for built-in types to make them weak-referenceable.

TaintWrapper exists solely to allow built-in types (int, str, list, dict, etc.)
to be used as keys in WeakKeyDictionary (TAINT_DICT). It stores NO taint itself -
all taint information is stored in TAINT_DICT.

Key principle: TaintWrapper objects are transparent proxies that delegate
all operations to the wrapped object. Most operations are handled by
AST transformation via exec_func, not by dunder methods here.
"""


class TaintWrapper:
    """
    Minimal wrapper for built-in types to make them weak-referenceable.

    Stores NO taint. All taint is in TAINT_DICT.
    Most operations go through AST rewrites, not dunder methods.
    """

    __slots__ = ("obj", "__weakref__")

    def __init__(self, obj):
        object.__setattr__(self, "obj", obj)

    # === Delegation ===

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "obj"), name)

    def __setattr__(self, name, value):
        if name == "obj":
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, "obj"), name, value)

    def __getitem__(self, key):
        return object.__getattribute__(self, "obj")[key]

    def __setitem__(self, key, value):
        object.__getattribute__(self, "obj")[key] = value

    def __delitem__(self, key):
        del object.__getattribute__(self, "obj")[key]

    # === Control flow (not AST-rewritten) ===

    def __bool__(self):
        return bool(object.__getattribute__(self, "obj"))

    def __iter__(self):
        obj = object.__getattribute__(self, "obj")
        import builtins
        from aco.server.ast_helpers import add_to_taint_dict_and_return, get_taint

        # Get this wrapper's taint to propagate to items
        try:
            shadow = builtins.TAINT_DICT.get(self, {})
            self_taint = shadow.get("self", [])
        except (TypeError, AttributeError):
            self_taint = []

        for item in obj:
            # Yield each item with the collection's taint
            yield add_to_taint_dict_and_return(item, taint=list(self_taint))

    def __len__(self):
        return len(object.__getattribute__(self, "obj"))

    def __index__(self):
        return object.__getattribute__(self, "obj").__index__()

    def __hash__(self):
        # Use object identity for hashing (needed for WeakKeyDictionary)
        return object.__hash__(self)

    # === Context manager ===

    def __enter__(self):
        return object.__getattribute__(self, "obj").__enter__()

    def __exit__(self, *args):
        return object.__getattribute__(self, "obj").__exit__(*args)

    # === Callable ===

    def __call__(self, *args, **kwargs):
        return object.__getattribute__(self, "obj")(*args, **kwargs)

    # === Serialization ===

    def __reduce__(self):
        return (lambda x: x, (object.__getattribute__(self, "obj"),))

    # === Debug ===

    def __repr__(self):
        return f"TaintWrapper({object.__getattribute__(self, 'obj')!r})"

    def __str__(self):
        return str(object.__getattribute__(self, "obj"))

    # === Type transparency ===

    @property
    def __class__(self):
        return object.__getattribute__(self, "obj").__class__


def untaint_if_needed(val, _seen=None):
    """
    Recursively unwrap TaintWrapper objects.

    Args:
        val: The value to untaint
        _seen: Set to track visited objects (prevents circular references)

    Returns:
        The unwrapped value
    """
    if _seen is None:
        _seen = set()

    obj_id = id(val)
    if obj_id in _seen:
        return val
    _seen.add(obj_id)

    if isinstance(val, TaintWrapper):
        return untaint_if_needed(object.__getattribute__(val, "obj"), _seen)

    if isinstance(val, dict):
        return {k: untaint_if_needed(v, _seen) for k, v in val.items()}
    if isinstance(val, list):
        return [untaint_if_needed(item, _seen) for item in val]
    if isinstance(val, tuple):
        return tuple(untaint_if_needed(item, _seen) for item in val)
    if isinstance(val, set):
        return {untaint_if_needed(item, _seen) for item in val}

    return val


def get_taint_origins(val, _seen=None):
    """
    Extract taint origins from TAINT_DICT.

    Args:
        val: The value to extract taint from
        _seen: Set to track visited objects (prevents circular references)

    Returns:
        List of taint origins found
    """
    if _seen is None:
        _seen = set()

    obj_id = id(val)
    if obj_id in _seen:
        return []
    _seen.add(obj_id)

    import builtins

    # Check TAINT_DICT for this object
    if hasattr(builtins, "TAINT_DICT"):
        try:
            if val in builtins.TAINT_DICT:
                shadow = builtins.TAINT_DICT[val]
                return list(shadow.get("self", []))
        except TypeError:
            pass

    # Check collections recursively
    origins = set()
    if isinstance(val, (list, tuple, set)):
        for item in val:
            origins.update(get_taint_origins(item, _seen))
    elif isinstance(val, dict):
        for v in val.values():
            origins.update(get_taint_origins(v, _seen))

    return list(origins)


# Legacy function for backwards compatibility during transition
def taint_wrap(obj, taint_origin=None, root_wrapper=None):
    """
    Legacy wrapper function - redirects to new TAINT_DICT approach.

    This function exists for backwards compatibility during the transition.
    New code should use add_to_taint_dict_and_return() instead.
    """
    from aco.server.ast_helpers import add_to_taint_dict_and_return

    if taint_origin is None:
        taint_origin = []
    elif isinstance(taint_origin, (int, str)):
        taint_origin = [taint_origin]

    return add_to_taint_dict_and_return(obj, taint=list(taint_origin))


def is_wrapped(obj):
    """Check if an object is a TaintWrapper."""
    return isinstance(obj, TaintWrapper)
