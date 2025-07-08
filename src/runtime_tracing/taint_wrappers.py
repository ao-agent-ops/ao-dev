import functools
import uuid
import collections.abc

def _merge_taint(origins):
    merged = set()
    for o in origins:
        if isinstance(o, (list, set)):
            merged.update(o)
        elif o is not None:
            merged.add(o)
    return list(merged)

class TaintedStr(str):
    def __new__(cls, value, taint_id=None, taint_origin=None):
        obj = str.__new__(cls, value)
        obj._taint_id = taint_id or str(uuid.uuid4())
        obj._taint_origin = taint_origin or obj._taint_id
        return obj

    def __add__(self, other):
        result = str.__add__(self, other)
        origins = _merge_taint([getattr(self, '_taint_origin', None), getattr(other, '_taint_origin', None)])
        return TaintedStr(result, taint_origin=origins)

    def __radd__(self, other):
        result = str.__add__(other, self)
        origins = _merge_taint([getattr(self, '_taint_origin', None), getattr(other, '_taint_origin', None)])
        return TaintedStr(result, taint_origin=origins)

    def __getitem__(self, key):
        result = str.__getitem__(self, key)
        return TaintedStr(result, taint_origin=self._taint_origin)

class TaintedInt(int):
    def __new__(cls, value, taint_id=None, taint_origin=None):
        obj = int.__new__(cls, value)
        obj._taint_id = taint_id or str(uuid.uuid4())
        obj._taint_origin = taint_origin or obj._taint_id
        return obj

    def __add__(self, other):
        result = int.__add__(self, other)
        origins = _merge_taint([getattr(self, '_taint_origin', None), getattr(other, '_taint_origin', None)])
        return TaintedInt(result, taint_origin=origins)

    def __radd__(self, other):
        result = int.__add__(other, self)
        origins = _merge_taint([getattr(self, '_taint_origin', None), getattr(other, '_taint_origin', None)])
        return TaintedInt(result, taint_origin=origins)

class TaintedFloat(float):
    def __new__(cls, value, taint_id=None, taint_origin=None):
        obj = float.__new__(cls, value)
        obj._taint_id = taint_id or str(uuid.uuid4())
        obj._taint_origin = taint_origin or obj._taint_id
        return obj

    def __add__(self, other):
        result = float.__add__(self, other)
        origins = _merge_taint([getattr(self, '_taint_origin', None), getattr(other, '_taint_origin', None)])
        return TaintedFloat(result, taint_origin=origins)

    def __radd__(self, other):
        result = float.__add__(other, self)
        origins = _merge_taint([getattr(self, '_taint_origin', None), getattr(other, '_taint_origin', None)])
        return TaintedFloat(result, taint_origin=origins)

class TaintedList(list):
    def __init__(self, value, taint_id=None, taint_origin=None):
        super().__init__(value)
        self._taint_id = taint_id or str(uuid.uuid4())
        self._taint_origin = taint_origin or self._taint_id

    def __getitem__(self, key):
        result = super().__getitem__(key)
        return taint_wrap(result, taint_origin=self._taint_origin)

    def append(self, item):
        super().append(item)
        if hasattr(item, '_taint_origin'):
            self._taint_origin = _merge_taint([self._taint_origin, item._taint_origin])

class TaintedDict(dict):
    def __init__(self, value, taint_id=None, taint_origin=None):
        super().__init__(value)
        self._taint_id = taint_id or str(uuid.uuid4())
        self._taint_origin = taint_origin or self._taint_id

    def __getitem__(self, key):
        result = super().__getitem__(key)
        return taint_wrap(result, taint_origin=self._taint_origin)

class TaintedOpenAIResponse:
    """
    Proxy for OpenAI response objects (or any object), tainting all attribute/item access.
    """
    def __init__(self, wrapped, taint_id=None, taint_origin=None):
        self._wrapped = wrapped
        self._taint_id = taint_id or str(uuid.uuid4())
        self._taint_origin = taint_origin or self._taint_id

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

# Utility functions
def is_tainted(obj):
    return hasattr(obj, '_taint_id')

def get_taint_origin(obj):
    return getattr(obj, '_taint_origin', None)

def is_openai_response(obj):
    # Heuristic: check for OpenAIObject or openai module, or fallback to user config
    cls = obj.__class__
    mod = cls.__module__
    name = cls.__name__
    if 'openai' in mod.lower() or 'openai' in name.lower():
        return True
    # Optionally, add more checks here
    return False

def taint_wrap(obj, taint_origin=None, _seen=None):
    """
    Recursively taint all strings, ints, floats, lists, dicts, Mapping and Sequence types, and user-defined object attributes.
    Handles cyclic references robustly. Taints OpenAIObject and similar types with a proxy.
    """
    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if obj_id in _seen:
        return obj
    _seen.add(obj_id)

    if is_tainted(obj):
        return obj
    if isinstance(obj, str):
        return TaintedStr(obj, taint_origin=taint_origin)
    if isinstance(obj, int):
        return TaintedInt(obj, taint_origin=taint_origin)
    if isinstance(obj, float):
        return TaintedFloat(obj, taint_origin=taint_origin)
    # Handle Mapping-like objects (including OpenAIObject)
    if isinstance(obj, collections.abc.Mapping):
        return TaintedDict({k: taint_wrap(v, taint_origin=taint_origin, _seen=_seen) for k, v in obj.items()}, taint_origin=taint_origin)
    # Handle Sequence-like objects (excluding str/bytes)
    if isinstance(obj, collections.abc.Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        return TaintedList([taint_wrap(x, taint_origin=taint_origin, _seen=_seen) for x in obj], taint_origin=taint_origin)
    # Recursively taint user-defined object attributes (e.g., OpenAIObject)
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
    # If it's an OpenAI response (or fallback for unknown types), wrap it:
    if is_openai_response(obj):
        return TaintedOpenAIResponse(obj, taint_origin=taint_origin)
    # fallback: if you want to taint all unknown objects, uncomment below
    # return TaintedOpenAIResponse(obj, taint_origin=taint_origin)
    return obj 