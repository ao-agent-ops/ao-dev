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

    def __getitem__(self, key):
        result = str.__getitem__(self, key)
        return TaintStr(result, self._taint_origin)

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