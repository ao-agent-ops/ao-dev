import functools
import uuid
import collections.abc

def get_origin_nodes(val):
    if hasattr(val, '_taint_origin') and val._taint_origin:
        return val._taint_origin.get('origin_nodes', [])
    return []

# Utility functions
def is_tainted(obj):
    return hasattr(obj, '_taint_origin') and bool(get_origin_nodes(obj))

def get_taint_origin(obj):
    if hasattr(obj, '_taint_origin'):
        return obj._taint_origin
    return None

def check_taint(val):
    # TODO: Isn't the return type either origin_list, or [origin_list], or {k: origin_list}, (or None). But it should always just be origin_list
    # Is tainted?
    if get_origin_nodes(val):
        return get_origin_nodes(val)
    # Is list or tuple with tainted entries?
    if isinstance(val, (list, tuple)):
        return [check_taint(v) for v in val]
    if isinstance(val, dict):
        return {k: check_taint(v) for k, v in val.items()}
    return None

def is_openai_response(obj):
    # Heuristic: check for OpenAIObject or openai module, or fallback to user config
    cls = obj.__class__
    mod = cls.__module__
    name = cls.__name__
    if 'openai' in mod.lower() or 'openai' in name.lower():
        return True
    # Optionally, add more checks here
    return False

# Taint-aware str
class TaintStr(str):
    def __new__(cls, value, taint_origin=None):
        obj = str.__new__(cls, value)
        if taint_origin is None:
            obj._taint_origin = {'origin_nodes': []}
        elif isinstance(taint_origin, dict):
            nodes = taint_origin.get('origin_nodes', [])
            if not isinstance(nodes, list):
                raise TypeError('origin_nodes must be a list')
            obj._taint_origin = dict(taint_origin)
        elif isinstance(taint_origin, (int, str)):
            obj._taint_origin = {'origin_nodes': [taint_origin]}
        elif isinstance(taint_origin, list):
            obj._taint_origin = {'origin_nodes': list(taint_origin)}
        else:
            raise TypeError(f'Unsupported taint_origin type: {type(taint_origin)}')
        return obj

    def __add__(self, other):
        result = str.__add__(self, other)
        nodes = set(get_origin_nodes(self)) | set(get_origin_nodes(other))
        return TaintStr(result, {'origin_nodes': list(nodes)})

    def __radd__(self, other):
        result = str.__add__(other, self)
        nodes = set(get_origin_nodes(self)) | set(get_origin_nodes(other))
        return TaintStr(result, {'origin_nodes': list(nodes)})

    def __format__(self, format_spec):
        # Handle f-string interpolation by preserving taint information
        result = str.__format__(self, format_spec)
        return TaintStr(result, self._taint_origin)

    def __getitem__(self, key):
        result = str.__getitem__(self, key)
        return TaintStr(result, self._taint_origin)

    def get_raw(self):
        return str(self)

class TaintInt(int):
    def __new__(cls, value, taint_origin=None):
        obj = int.__new__(cls, value)
        if taint_origin is None:
            obj._taint_origin = {'origin_nodes': []}
        elif isinstance(taint_origin, dict):
            nodes = taint_origin.get('origin_nodes', [])
            if not isinstance(nodes, list):
                raise TypeError('origin_nodes must be a list')
            obj._taint_origin = dict(taint_origin)
        elif isinstance(taint_origin, (int, str)):
            obj._taint_origin = {'origin_nodes': [taint_origin]}
        elif isinstance(taint_origin, list):
            obj._taint_origin = {'origin_nodes': list(taint_origin)}
        else:
            raise TypeError(f'Unsupported taint_origin type: {type(taint_origin)}')
        return obj

    def __add__(self, other):
        result = int.__add__(self, other)
        nodes = set(get_origin_nodes(self)) | set(get_origin_nodes(other))
        return TaintInt(result, {'origin_nodes': list(nodes)})

    def __radd__(self, other):
        result = int.__add__(other, self)
        nodes = set(get_origin_nodes(self)) | set(get_origin_nodes(other))
        return TaintInt(result, {'origin_nodes': list(nodes)})

    def get_raw(self):
        return int(self)

class TaintFloat(float):
    def __new__(cls, value, taint_origin=None):
        obj = float.__new__(cls, value)
        if taint_origin is None:
            obj._taint_origin = {'origin_nodes': []}
        elif isinstance(taint_origin, dict):
            nodes = taint_origin.get('origin_nodes', [])
            if not isinstance(nodes, list):
                raise TypeError('origin_nodes must be a list')
            obj._taint_origin = dict(taint_origin)
        elif isinstance(taint_origin, (int, str)):
            obj._taint_origin = {'origin_nodes': [taint_origin]}
        elif isinstance(taint_origin, list):
            obj._taint_origin = {'origin_nodes': list(taint_origin)}
        else:
            raise TypeError(f'Unsupported taint_origin type: {type(taint_origin)}')
        return obj

    def __add__(self, other):
        result = float.__add__(self, other)
        nodes = set(get_origin_nodes(self)) | set(get_origin_nodes(other))
        return TaintFloat(result, {'origin_nodes': list(nodes)})

    def __radd__(self, other):
        result = float.__add__(other, self)
        nodes = set(get_origin_nodes(self)) | set(get_origin_nodes(other))
        return TaintFloat(result, {'origin_nodes': list(nodes)})

    def get_raw(self):
        return float(self)

class TaintList(list):
    def __init__(self, value, taint_origin=None):
        list.__init__(self, value)
        if taint_origin is None:
            self._taint_origin = {'origin_nodes': []}
        elif isinstance(taint_origin, dict):
            nodes = taint_origin.get('origin_nodes', [])
            if not isinstance(nodes, list):
                raise TypeError('origin_nodes must be a list')
            self._taint_origin = dict(taint_origin)
        elif isinstance(taint_origin, (int, str)):
            self._taint_origin = {'origin_nodes': [taint_origin]}
        elif isinstance(taint_origin, list):
            self._taint_origin = {'origin_nodes': list(taint_origin)}
        else:
            raise TypeError(f'Unsupported taint_origin type: {type(taint_origin)}')
        # Merge in taint from all items
        for v in value:
            self._taint_origin['origin_nodes'] = list(set(self._taint_origin['origin_nodes']) | set(get_origin_nodes(v)))

    def append(self, item):
        list.append(self, item)
        self._taint_origin['origin_nodes'] = list(set(self._taint_origin['origin_nodes']) | set(get_origin_nodes(item)))

    def extend(self, items):
        list.extend(self, items)
        for item in items:
            self._taint_origin['origin_nodes'] = list(set(self._taint_origin['origin_nodes']) | set(get_origin_nodes(item)))

    def get_raw(self):
        return [x.get_raw() if hasattr(x, 'get_raw') else x for x in self]

class TaintDict(dict):
    def __init__(self, value, taint_origin=None):
        dict.__init__(self, value)
        if taint_origin is None:
            self._taint_origin = {'origin_nodes': []}
        elif isinstance(taint_origin, dict):
            nodes = taint_origin.get('origin_nodes', [])
            if not isinstance(nodes, list):
                raise TypeError('origin_nodes must be a list')
            self._taint_origin = dict(taint_origin)
        elif isinstance(taint_origin, (int, str)):
            self._taint_origin = {'origin_nodes': [taint_origin]}
        elif isinstance(taint_origin, list):
            self._taint_origin = {'origin_nodes': list(taint_origin)}
        else:
            raise TypeError(f'Unsupported taint_origin type: {type(taint_origin)}')
        # Merge in taint from all values
        for v in value.values():
            self._taint_origin['origin_nodes'] = list(set(self._taint_origin['origin_nodes']) | set(get_origin_nodes(v)))

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self._taint_origin['origin_nodes'] = list(set(self._taint_origin['origin_nodes']) | set(get_origin_nodes(value)))

    def get_raw(self):
        return {k: v.get_raw() if hasattr(v, 'get_raw') else v for k, v in self.items()}

class TaintedOpenAIResponse:
    """
    Proxy for OpenAI response objects (or any object), tainting all attribute/item access.
    """
    def __init__(self, wrapped, taint_origin=None):
        self._wrapped = wrapped
        if taint_origin is None:
            self._taint_origin = {'origin_nodes': []}
        elif isinstance(taint_origin, dict):
            nodes = taint_origin.get('origin_nodes', [])
            if not isinstance(nodes, list):
                raise TypeError('origin_nodes must be a list')
            self._taint_origin = dict(taint_origin)
        elif isinstance(taint_origin, (int, str)):
            self._taint_origin = {'origin_nodes': [taint_origin]}
        elif isinstance(taint_origin, list):
            self._taint_origin = {'origin_nodes': list(taint_origin)}
        else:
            raise TypeError(f'Unsupported taint_origin type: {type(taint_origin)}')

    def __getattr__(self, name):
        value = getattr(self._wrapped, name)
        return taint_wrap(value, taint_origin=self._taint_origin)

    def __getitem__(self, key):
        value = self._wrapped[key]
        return taint_wrap(value, taint_origin=self._taint_origin)

    def __repr__(self):
        return f"TaintedOpenAIResponse({repr(self._wrapped)}, taint_origin={self._taint_origin})"

    def __str__(self):
        return str(self._wrapped)

    def __dir__(self):
        return dir(self._wrapped)

    def __iter__(self):
        return iter(self._wrapped)

    def __contains__(self, item):
        return item in self._wrapped

    def get_raw(self):
        return self._wrapped

def taint_wrap(obj, taint_origin=None, _seen=None):
    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if obj_id in _seen:
        return obj
    _seen.add(obj_id)

    if is_tainted(obj):
        return obj
    if isinstance(obj, str):
        return TaintStr(obj, taint_origin=taint_origin)
    if isinstance(obj, int):
        return TaintInt(obj, taint_origin=taint_origin)
    if isinstance(obj, float):
        return TaintFloat(obj, taint_origin=taint_origin)
    if is_openai_response(obj):
        return TaintedOpenAIResponse(obj, taint_origin=taint_origin)
    if isinstance(obj, collections.abc.Mapping):
        return TaintDict({k: taint_wrap(v, taint_origin=taint_origin, _seen=_seen) for k, v in obj.items()}, taint_origin=taint_origin)
    if isinstance(obj, collections.abc.Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        return TaintList([taint_wrap(x, taint_origin=taint_origin, _seen=_seen) for x in obj], taint_origin=taint_origin)
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        for attr in list(vars(obj)):
            try:
                setattr(obj, attr, taint_wrap(getattr(obj, attr), taint_origin=taint_origin, _seen=_seen))
            except Exception:
                pass
        return obj
    if hasattr(obj, "__slots__"):
        for slot in obj.__slots__:
            try:
                val = getattr(obj, slot)
                setattr(obj, slot, taint_wrap(val, taint_origin=taint_origin, _seen=_seen))
            except Exception:
                pass
        return obj
    return obj

class TaintStringContext:
    """
    Context manager for taint-aware string operations.
    This provides a way to temporarily intercept string operations to preserve taint.
    """
    def __init__(self):
        self.original_str = str
        self.original_format = str.format
        self._taint_stack = []
    
    def __enter__(self):
        # Store current taint context
        self._taint_stack.append(set())
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore previous taint context
        if self._taint_stack:
            self._taint_stack.pop()
    
    def add_taint(self, taint_origin):
        """Add taint origin to current context."""
        if self._taint_stack:
            if isinstance(taint_origin, dict) and 'origin_nodes' in taint_origin:
                self._taint_stack[-1].update(taint_origin['origin_nodes'])
            elif isinstance(taint_origin, (list, tuple)):
                self._taint_stack[-1].update(taint_origin)
            elif isinstance(taint_origin, (str, int)):
                self._taint_stack[-1].add(taint_origin)
    
    def get_current_taint(self):
        """Get current taint origins."""
        if self._taint_stack:
            return list(self._taint_stack[-1])
        return []

def taint_format(template, *args, **kwargs):
    """
    Taint-aware string formatting that preserves taint information.
    
    Usage:
        tainted = TaintStr("42", {'origin_nodes': ['node1']})
        result = taint_format("The answer is {}", tainted)
        # result is a TaintStr with taint from 'node1'
    """
    # Collect all taint origins from args and kwargs
    all_origins = set()
    
    for arg in args:
        origins = get_origin_nodes(arg)
        all_origins.update(origins)
    
    for value in kwargs.values():
        origins = get_origin_nodes(value)
        all_origins.update(origins)
    
    # Format the string normally
    formatted = template.format(*args, **kwargs)
    
    # Return as TaintStr with combined origins
    return TaintStr(formatted, {'origin_nodes': list(all_origins)}) 

def taint_format_advanced(template, *args, **kwargs):
    """
    Advanced taint-aware formatting that can handle complex cases.
    """
    with TaintStringContext() as ctx:
        # Add taint from all arguments
        for arg in args:
            ctx.add_taint(get_origin_nodes(arg))
        
        for value in kwargs.values():
            ctx.add_taint(get_origin_nodes(value))
        
        # Format the string
        result = template.format(*args, **kwargs)
        
        # Return with combined taint
        return TaintStr(result, {'origin_nodes': ctx.get_current_taint()}) 