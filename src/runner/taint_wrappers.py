import collections.abc
import ast


# Utility functions
def untaint_if_needed(val, _seen=None):
    """
    Recursively remove taint from objects and nested data structures.

    Args:
        val: The value to untaint
        _seen: Set to track visited objects (prevents circular references)

    Returns:
        The untainted version of the value
    """
    if _seen is None:
        _seen = set()

    obj_id = id(val)
    if obj_id in _seen:
        return val
    _seen.add(obj_id)

    # If object has get_raw method (tainted), use it
    if hasattr(val, "get_raw"):
        return untaint_if_needed(val.get_raw(), _seen)

    # Handle nested data structures
    if isinstance(val, dict):
        return {k: untaint_if_needed(v, _seen) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        result = [untaint_if_needed(item, _seen) for item in val]
        return tuple(result) if isinstance(val, tuple) else result
    elif isinstance(val, set):
        return {untaint_if_needed(item, _seen) for item in val}
    elif hasattr(val, "__dict__") and not isinstance(val, type):
        # Handle custom objects with attributes, e.g., (MyObj(a=5, b=1)).
        try:
            new_obj = val.__class__.__new__(val.__class__)
            for attr, value in val.__dict__.items():
                setattr(new_obj, attr, untaint_if_needed(value, _seen))
            return new_obj
        except Exception:
            return val
    elif hasattr(val, "__slots__"):
        # Handle objects with __slots__ (some objects have __slots__ but no __dict__).
        try:
            new_obj = val.__class__.__new__(val.__class__)
            for slot in val.__slots__:
                if hasattr(val, slot):
                    value = getattr(val, slot)
                    setattr(new_obj, slot, untaint_if_needed(value, _seen))
            return new_obj
        except Exception:
            return val

    # Return primitive types and other objects as-is
    return val


def is_tainted(obj):
    return hasattr(obj, "_taint_origin") and bool(get_taint_origins(obj))


def get_taint_origins(val, _seen=None):
    """
    Return a flat list of all taint origins for the input, including nested objects.

    Args:
        val: The value to extract taint origins from
        _seen: Set to track visited objects (prevents circular references)

    Returns:
        List of taint origins found in the value and its nested structures
    """
    if _seen is None:
        _seen = set()

    obj_id = id(val)
    if obj_id in _seen:
        return []
    _seen.add(obj_id)

    # Check if object has direct taint
    if hasattr(val, "_taint_origin") and val._taint_origin is not None:
        return list(val._taint_origin)

    # Handle nested data structures
    origins = set()

    if isinstance(val, (list, tuple, set)):
        for v in val:
            origins.update(get_taint_origins(v, _seen))
    elif isinstance(val, dict):
        for v in val.values():
            origins.update(get_taint_origins(v, _seen))
    elif hasattr(val, "__dict__") and not isinstance(val, type):
        # Handle custom objects with attributes
        for attr_val in val.__dict__.values():
            origins.update(get_taint_origins(attr_val, _seen))
    elif hasattr(val, "__slots__"):
        # Handle objects with __slots__
        for slot in val.__slots__:
            if hasattr(val, slot):
                slot_val = getattr(val, slot)
                origins.update(get_taint_origins(slot_val, _seen))

    return list(origins)


def is_openai_response(obj):
    # Heuristic: check for OpenAIObject or openai module, or fallback to user config
    cls = obj.__class__
    mod = cls.__module__
    name = cls.__name__
    if "openai" in mod.lower() or "openai" in name.lower():
        return True
    # Optionally, add more checks here
    return False


# Taint-aware str
class TaintStr(str):
    def __new__(cls, value, taint_origin=None):
        obj = str.__new__(cls, value)
        if taint_origin is None:
            obj._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            obj._taint_origin = [taint_origin]
        elif isinstance(taint_origin, list):
            obj._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")
        return obj

    def __add__(self, other):
        result = str.__add__(self, other)
        adjusted_other_taints = increase_position_taints(other, len(self))
        nodes = set(get_taint_origins(self)) | set(adjusted_other_taints)
        return TaintStr(result, list(nodes))

    def __radd__(self, other):
        result = str.__add__(other, self)
        adjusted_self_taints = increase_position_taints(self, len(other))
        nodes = set(get_taint_origins(other)) | set(adjusted_self_taints)
        return TaintStr(result, list(nodes))

    def __format__(self, format_spec):
        result = str.__format__(self, format_spec)
        return TaintStr(result, self._taint_origin)

    def __getitem__(self, key):
        result = str.__getitem__(self, key)
        adjusted_taints = []
        for taint_origin in get_taint_origins(self):
            if is_random_taint(taint_origin):
                new_taint = None
                pos_list = extract_position_from_random_taint(taint_origin)
                if isinstance(key, slice):
                    indices_key = list(range(0, len(self)))[key]
                    overlap = [i for i in range(pos_list[0], pos_list[1]) if i in indices_key]
                    if overlap != []:
                        new_taint = f"[position]{str([min(overlap), max(overlap)])}"
                else:
                    # key: int
                    if key >= pos_list[0] and key < pos_list[1]:
                        new_taint = f"[position]{str([key, key])}"
                if new_taint is not None:
                    adjusted_taints.append(new_taint)
            else:
                adjusted_taints.append(taint_origin)
        return TaintStr(result, adjusted_taints)

    def __mod__(self, other):
        result = str.__mod__(self, other)
        if result is NotImplemented:
            return NotImplemented
        nodes = set(get_taint_origins(self))
        if isinstance(other, (tuple, list)):
            for o in other:
                nodes.update(get_taint_origins(o))
        else:
            nodes.update(get_taint_origins(other))
        return TaintStr(result, list(nodes))

    def __rmod__(self, other):
        result = str.__mod__(other, self)
        if result is NotImplemented:
            return NotImplemented
        nodes = set(get_taint_origins(self)) | set(get_taint_origins(other))
        return TaintStr(result, list(nodes))

    def encode(self, *args, **kwargs):
        return str(self).encode(*args, **kwargs)

    def decode(self, *args, **kwargs):
        return str(self).decode(*args, **kwargs)

    def join(self, iterable):
        joined = str(self).join([str(x) for x in iterable])
        nodes = set(get_taint_origins(self))
        for x in iterable:
            nodes.update(get_taint_origins(x))
        return TaintStr(joined, list(nodes))

    def __str__(self):
        return str.__str__(self)

    def __repr__(self):
        return f"TaintStr({super().__repr__()}, taint_origin={self._taint_origin})"

    def get_raw(self):
        return str(self)

    # Add more methods for compatibility
    def upper(self, *args, **kwargs):
        return TaintStr(str.upper(self, *args, **kwargs), self._taint_origin)

    def lower(self, *args, **kwargs):
        return TaintStr(str.lower(self, *args, **kwargs), self._taint_origin)

    def strip(self, *args, **kwargs):
        return TaintStr(str.strip(self, *args, **kwargs), self._taint_origin)

    def lstrip(self, *args, **kwargs):
        return TaintStr(str.lstrip(self, *args, **kwargs), self._taint_origin)

    def rstrip(self, *args, **kwargs):
        return TaintStr(str.rstrip(self, *args, **kwargs), self._taint_origin)

    def replace(self, old, new, *args, **kwargs):
        result = str.replace(self, old, new, *args, **kwargs)
        nodes = set(get_taint_origins(self)) | set(get_taint_origins(new))
        return TaintStr(result, list(nodes))

    def split(self, *args, **kwargs):
        return [TaintStr(s, self._taint_origin) for s in str.split(self, *args, **kwargs)]

    def capitalize(self, *args, **kwargs):
        return TaintStr(str.capitalize(self, *args, **kwargs), self._taint_origin)

    def title(self, *args, **kwargs):
        return TaintStr(str.title(self, *args, **kwargs), self._taint_origin)

    def startswith(self, *args, **kwargs):
        return str.startswith(self, *args, **kwargs)

    def endswith(self, *args, **kwargs):
        return str.endswith(self, *args, **kwargs)

    def find(self, *args, **kwargs):
        return str.find(self, *args, **kwargs)

    def index(self, *args, **kwargs):
        return str.index(self, *args, **kwargs)

    def count(self, *args, **kwargs):
        return str.count(self, *args, **kwargs)

    def isdigit(self, *args, **kwargs):
        return str.isdigit(self, *args, **kwargs)

    def isalpha(self, *args, **kwargs):
        return str.isalpha(self, *args, **kwargs)

    def isalnum(self, *args, **kwargs):
        return str.isalnum(self, *args, **kwargs)

    def isnumeric(self, *args, **kwargs):
        return str.isnumeric(self, *args, **kwargs)

    def islower(self, *args, **kwargs):
        return str.islower(self, *args, **kwargs)

    def isupper(self, *args, **kwargs):
        return str.isupper(self, *args, **kwargs)

    def isspace(self, *args, **kwargs):
        return str.isspace(self, *args, **kwargs)

    def __hash__(self):
        return str.__hash__(self)


class TaintInt(int):
    def __new__(cls, value, taint_origin=None):
        obj = int.__new__(cls, value)
        if taint_origin is None:
            obj._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            obj._taint_origin = [taint_origin]
        elif isinstance(taint_origin, list):
            obj._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")
        return obj

    def _propagate_taint(self, other):
        nodes = set(get_taint_origins(self)) | set(get_taint_origins(other))
        return list(nodes)

    # Arithmetic operators
    def __add__(self, other):
        result = int.__add__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __radd__(self, other):
        result = int.__add__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __sub__(self, other):
        result = int.__sub__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rsub__(self, other):
        result = int.__sub__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __mul__(self, other):
        result = int.__mul__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rmul__(self, other):
        result = int.__mul__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __floordiv__(self, other):
        result = int.__floordiv__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rfloordiv__(self, other):
        result = int.__floordiv__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __truediv__(self, other):
        result = int.__truediv__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintFloat(result, self._propagate_taint(other))

    def __rtruediv__(self, other):
        result = int.__truediv__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintFloat(result, self._propagate_taint(other))

    def __mod__(self, other):
        result = int.__mod__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rmod__(self, other):
        result = int.__mod__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __pow__(self, other, modulo=None):
        result = (
            int.__pow__(self, other, modulo) if modulo is not None else int.__pow__(self, other)
        )
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rpow__(self, other, modulo=None):
        result = (
            int.__pow__(other, self, modulo) if modulo is not None else int.__pow__(other, self)
        )
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __neg__(self):
        result = int.__neg__(self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, get_taint_origins(self))

    def __pos__(self):
        result = int.__pos__(self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, get_taint_origins(self))

    def __abs__(self):
        result = int.__abs__(self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, get_taint_origins(self))

    def __invert__(self):
        result = int.__invert__(self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, get_taint_origins(self))

    def __and__(self, other):
        result = int.__and__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rand__(self, other):
        result = int.__and__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __or__(self, other):
        result = int.__or__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __ror__(self, other):
        result = int.__or__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __xor__(self, other):
        result = int.__xor__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rxor__(self, other):
        result = int.__xor__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __lshift__(self, other):
        result = int.__lshift__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rlshift__(self, other):
        result = int.__lshift__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rshift__(self, other):
        result = int.__rshift__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rrshift__(self, other):
        result = int.__rshift__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __matmul__(self, other):
        result = int.__matmul__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rmatmul__(self, other):
        result = int.__matmul__(other, self)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    # Conversion and index
    def __int__(self):
        return int(self)

    def __float__(self):
        return float(self)

    def __index__(self):
        return int(self)

    # Comparison operators (return bool)
    def __eq__(self, other):
        return int.__eq__(self, other)

    def __ne__(self, other):
        return int.__ne__(self, other)

    def __lt__(self, other):
        return int.__lt__(self, other)

    def __le__(self, other):
        return int.__le__(self, other)

    def __gt__(self, other):
        return int.__gt__(self, other)

    def __ge__(self, other):
        return int.__ge__(self, other)

    # Boolean context
    def __bool__(self):
        return int.__bool__(self)

    def get_raw(self):
        return int(self)


class TaintFloat(float):
    def __new__(cls, value, taint_origin=None):
        obj = float.__new__(cls, value)
        if taint_origin is None:
            obj._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            obj._taint_origin = [taint_origin]
        elif isinstance(taint_origin, list):
            obj._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")
        return obj

    def _propagate_taint(self, other):
        nodes = set(get_taint_origins(self)) | set(get_taint_origins(other))
        return list(nodes)

    # Arithmetic operators
    def __add__(self, other):
        result = float.__add__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __radd__(self, other):
        result = float.__add__(other, self)
        return TaintFloat(result, self._propagate_taint(other))

    def __sub__(self, other):
        result = float.__sub__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __rsub__(self, other):
        result = float.__sub__(other, self)
        return TaintFloat(result, self._propagate_taint(other))

    def __mul__(self, other):
        result = float.__mul__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __rmul__(self, other):
        result = float.__mul__(other, self)
        return TaintFloat(result, self._propagate_taint(other))

    def __floordiv__(self, other):
        result = float.__floordiv__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __rfloordiv__(self, other):
        result = float.__floordiv__(other, self)
        return TaintFloat(result, self._propagate_taint(other))

    def __truediv__(self, other):
        result = float.__truediv__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __rtruediv__(self, other):
        result = float.__truediv__(other, self)
        return TaintFloat(result, self._propagate_taint(other))

    def __mod__(self, other):
        result = float.__mod__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __rmod__(self, other):
        result = float.__mod__(other, self)
        return TaintFloat(result, self._propagate_taint(other))

    def __pow__(self, other, modulo=None):
        result = (
            float.__pow__(self, other, modulo) if modulo is not None else float.__pow__(self, other)
        )
        return TaintFloat(result, self._propagate_taint(other))

    def __rpow__(self, other, modulo=None):
        result = (
            float.__pow__(other, self, modulo) if modulo is not None else float.__pow__(other, self)
        )
        return TaintFloat(result, self._propagate_taint(other))

    def __neg__(self):
        return TaintFloat(float.__neg__(self), get_taint_origins(self))

    def __pos__(self):
        return TaintFloat(float.__pos__(self), get_taint_origins(self))

    def __abs__(self):
        return TaintFloat(float.__abs__(self), get_taint_origins(self))

    # Conversion and index
    def __int__(self):
        return int(self)

    def __float__(self):
        return float(self)

    def __index__(self):
        return int(self)

    # Comparison operators (return bool)
    def __eq__(self, other):
        return float.__eq__(self, other)

    def __ne__(self, other):
        return float.__ne__(self, other)

    def __lt__(self, other):
        return float.__lt__(self, other)

    def __le__(self, other):
        return float.__le__(self, other)

    def __gt__(self, other):
        return float.__gt__(self, other)

    def __ge__(self, other):
        return float.__ge__(self, other)

    # Boolean context
    def __bool__(self):
        return float.__bool__(self)

    def get_raw(self):
        return float(self)


class TaintList(list):
    def __init__(self, value, taint_origin=None):
        list.__init__(self, value)
        if taint_origin is None:
            self._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            self._taint_origin = [taint_origin]
        elif isinstance(taint_origin, list):
            self._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")
        # Merge in taint from all items
        for v in value:
            self._taint_origin = list(set(self._taint_origin) | set(get_taint_origins(v)))

    def _merge_taint_from(self, items):
        for v in items:
            self._taint_origin = list(set(self._taint_origin) | set(get_taint_origins(v)))

    def append(self, item):
        list.append(self, item)
        self._merge_taint_from([item])

    def extend(self, items):
        list.extend(self, items)
        self._merge_taint_from(items)

    def __setitem__(self, key, value):
        list.__setitem__(self, key, value)
        # key can be int or slice
        if isinstance(key, slice):
            self._merge_taint_from(value)
        else:
            self._merge_taint_from([value])

    def __delitem__(self, key):
        list.__delitem__(self, key)
        # Recompute taint from all items
        self._taint_origin = []
        self._merge_taint_from(self)

    def insert(self, index, item):
        list.insert(self, index, item)
        self._merge_taint_from([item])

    def pop(self, index=-1):
        item = list.pop(self, index)
        # Recompute taint from all items
        self._taint_origin = []
        self._merge_taint_from(self)
        return item

    def remove(self, value):
        list.remove(self, value)
        # Recompute taint from all items
        self._taint_origin = []
        self._merge_taint_from(self)

    def clear(self):
        list.clear(self)
        self._taint_origin = []

    def __iadd__(self, other):
        list.__iadd__(self, other)
        self._merge_taint_from(other)
        return self

    def __imul__(self, other):
        # Multiplying a list by n doesn't add new taint, but just repeat
        list.__imul__(self, other)
        # No new taint to add
        return self

    def get_raw(self):
        return [x.get_raw() if hasattr(x, "get_raw") else x for x in self]


class TaintDict(dict):
    def __init__(self, value, taint_origin=None):
        dict.__init__(self, value)
        if taint_origin is None:
            self._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            self._taint_origin = [taint_origin]
        elif isinstance(taint_origin, list):
            self._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")
        # Merge in taint from all values
        for v in value.values():
            self._taint_origin = list(set(self._taint_origin) | set(get_taint_origins(v)))

    def _merge_taint_from(self, values):
        for v in values:
            self._taint_origin = list(set(self._taint_origin) | set(get_taint_origins(v)))

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)
        self._merge_taint_from([value])

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        # Recompute taint from all values
        self._taint_origin = []
        self._merge_taint_from(self.values())

    def update(self, *args, **kwargs):
        dict.update(self, *args, **kwargs)
        # Merge taint from all new values
        if args:
            if isinstance(args[0], dict):
                self._merge_taint_from(args[0].values())
            else:
                self._merge_taint_from([v for k, v in args[0]])
        if kwargs:
            self._merge_taint_from(kwargs.values())

    def setdefault(self, key, default=None):
        if key not in self:
            self._merge_taint_from([default])
        return dict.setdefault(self, key, default)

    def pop(self, key, *args):
        value = dict.pop(self, key, *args)
        # Recompute taint from all values
        self._taint_origin = []
        self._merge_taint_from(self.values())
        return value

    def popitem(self):
        item = dict.popitem(self)
        # Recompute taint from all values
        self._taint_origin = []
        self._merge_taint_from(self.values())
        return item

    def clear(self):
        dict.clear(self)
        self._taint_origin = []

    def get_raw(self):
        return {k: v.get_raw() if hasattr(v, "get_raw") else v for k, v in self.items()}


class TaintedOpenAIObject:
    """
    Proxy for OpenAI SDK objects (Response, Assistant, etc.), tainting all attribute/item access.
    """

    def __init__(self, wrapped, taint_origin=None):
        self._wrapped = wrapped
        if taint_origin is None:
            self._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            self._taint_origin = [taint_origin]
        elif isinstance(taint_origin, list):
            self._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")

    def __getattr__(self, name):
        value = getattr(self._wrapped, name)
        wrapped_value = taint_wrap(value, taint_origin=self._taint_origin)
        return wrapped_value

    def __getitem__(self, key):
        value = self._wrapped[key]
        return taint_wrap(value, taint_origin=self._taint_origin)

    def __repr__(self):
        return f"TaintedOpenAIObject({repr(self._wrapped)}, taint_origin={self._taint_origin})"

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

    def __class_getitem__(cls, item):
        # Delegate class subscription to the wrapped class
        return cls._wrapped.__class_getitem__(item)

    def __reduce__(self):
        # For pickle/copy operations, return the wrapped object
        return (lambda x: x, (self._wrapped,))

    def __copy__(self):
        # For shallow copy, return wrapped object
        return self._wrapped

    def __deepcopy__(self, memo):
        # For deep copy, return wrapped object
        import copy

        return copy.deepcopy(self._wrapped, memo)

    def __instancecheck__(self, instance):
        # Delegate isinstance checks to wrapped object
        return isinstance(instance, self._wrapped.__class__)

    def __subclasscheck__(self, subclass):
        # Delegate issubclass checks to wrapped object
        return issubclass(subclass, self._wrapped.__class__)

    def __bool__(self):
        # Delegate boolean evaluation to wrapped object
        return bool(self._wrapped)

    def __len__(self):
        # Delegate len() to wrapped object
        return len(self._wrapped)

    def __hash__(self):
        # Delegate hash() to wrapped object
        return hash(self._wrapped)

    def __eq__(self, other):
        # Compare with the wrapped object
        if isinstance(other, TaintedOpenAIObject):
            return self._wrapped == other._wrapped
        return self._wrapped == other

    def __ne__(self, other):
        return not self.__eq__(other)

    # Make this object more transparent to type checkers and validation libraries
    @property
    def __class__(self):
        # This makes isinstance() checks work with the wrapped object's class
        return self._wrapped.__class__

    @__class__.setter
    def __class__(self, value):
        # Allow class assignment (some libraries do this)
        self._wrapped.__class__ = value


# Helper to detect OpenAI SDK objects (Response, Assistant, etc.)
def is_openai_sdk_object(obj):
    cls = obj.__class__
    mod = cls.__module__
    # Covers openai.types.responses.response, openai.types.beta.assistant, etc.
    return mod.startswith("openai.types.")


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
    if is_openai_sdk_object(obj):
        return TaintedOpenAIObject(obj, taint_origin=taint_origin)
    if isinstance(obj, collections.abc.Mapping):
        return TaintDict(
            {k: taint_wrap(v, taint_origin=taint_origin, _seen=_seen) for k, v in obj.items()},
            taint_origin=taint_origin,
        )
    if isinstance(obj, collections.abc.Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        return TaintList(
            [taint_wrap(x, taint_origin=taint_origin, _seen=_seen) for x in obj],
            taint_origin=taint_origin,
        )
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        for attr in list(vars(obj)):
            try:
                setattr(
                    obj,
                    attr,
                    taint_wrap(getattr(obj, attr), taint_origin=taint_origin, _seen=_seen),
                )
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


def taint_format(template, *args, **kwargs):
    """
    Taint-aware string formatting that preserves taint information.
    Usage:
        tainted = TaintStr("42", ["node1"])
        result = taint_format("The answer is {}", tainted)
        # result is a TaintStr with taint from 'node1'
    """
    # Collect all taint origins from args and kwargs
    all_origins = set()
    for arg in args:
        origins = get_taint_origins(arg)
        all_origins.update(origins)
    for value in kwargs.values():
        origins = get_taint_origins(value)
        all_origins.update(origins)
    # Format the string normally
    formatted = template.format(*args, **kwargs)
    # Return as TaintStr with combined origins
    return TaintStr(formatted, list(all_origins))


def is_random_taint(taint_origin):
    """Check if a taint origin represents a random taint with position information."""
    return isinstance(taint_origin, str) and "[random]" in taint_origin


def extract_position_from_random_taint(taint_origin):
    """Extract position list from a random taint origin."""
    return ast.literal_eval(taint_origin.split("[random]")[1])


def increase_position_taints(obj: str | TaintStr, offs: int) -> list:
    """
    Increase position taints in an object's taint origins by a given offset.

    Args:
        obj: The object to extract and adjust taint origins from
        offs: The offset to add to position-based taints

    Returns:
        List of adjusted taint origins
    """
    adjusted_taints = []
    for taint_origin in get_taint_origins(obj):
        if is_random_taint(taint_origin):
            pos_list = extract_position_from_random_taint(taint_origin)
            pos_list = list(map(lambda p: p + offs, pos_list))
            adjusted_taints.append(f"[random]{str(pos_list)}")
        else:
            adjusted_taints.append(taint_origin)
    return adjusted_taints


def set_position_taints(obj, start_pos: int, end_pos: int) -> list:
    """
    Set position taints for an object to specific start/end positions.

    Args:
        obj: The object to extract taint origins from
        start_pos: The start position in the final result
        end_pos: The end position in the final result

    Returns:
        List of taint origins with position taints set to the specified range.
        Returns empty list if obj is not tainted or has no position taints.
    """
    taint_origins = get_taint_origins(obj)

    # Create new taint list with updated positions
    new_taints = []
    for taint_origin in taint_origins:
        if is_random_taint(taint_origin):
            # Replace position with new range
            new_taints.append(f"[random]{str([start_pos, end_pos])}")
        else:
            # Keep non-position taints as-is
            new_taints.append(taint_origin)

    return new_taints
