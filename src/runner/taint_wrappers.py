import collections.abc
import ast
import re


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
    """
    Check if an object has taint information.

    Args:
        obj: The object to check for taint

    Returns:
        True if the object has taint origins, False otherwise
    """
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
    """
    Check if an object is an OpenAI SDK response object.

    Uses heuristics to detect OpenAI SDK objects by checking the module and class name.

    Args:
        obj: The object to check

    Returns:
        True if the object appears to be from the OpenAI SDK, False otherwise
    """
    # Heuristic: check for OpenAIObject or openai module, or fallback to user config
    cls = obj.__class__
    mod = cls.__module__
    name = cls.__name__
    if "openai" in mod.lower() or "openai" in name.lower():
        return True
    # Optionally, add more checks here
    return False


class Position:
    def __init__(self, start: int, stop: int):
        self.start = start
        self.stop = stop

    def shift(self, offset: int):
        self.start += offset
        self.stop += offset

    def set_pos(self, new_pos: list | tuple):
        assert len(new_pos) == 2, "length of pos must be 2"
        assert new_pos[0] <= new_pos[1], "pos must be increasing"
        self.start, self.stop = new_pos

    def __repr__(self):
        return f"{self.start}:{self.stop}"


# Taint-aware str
class TaintStr(str):
    def __new__(cls, value, taint_origin=None, random_pos=None):
        obj = str.__new__(cls, value)
        if taint_origin is None:
            obj._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            obj._taint_origin = [taint_origin]
        elif isinstance(taint_origin, list):
            obj._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")

        if random_pos is None:
            obj._random_positions = []
        elif isinstance(random_pos, Position):
            obj._random_positions = [random_pos]
        elif isinstance(random_pos, list):
            obj._random_positions = list(random_pos)
        else:
            raise NotImplementedError(
                f"Creating TaintStr with {random_pos} as random pos not implemented"
            )
        return obj

    def __add__(self, other):
        result = str.__add__(self, other)
        shift_position_taints(other, len(self))
        nodes = set(get_taint_origins(self)) | set(get_taint_origins(other))
        random_positions = get_random_positions(self) + get_random_positions(other)
        return TaintStr(result, taint_origin=list(nodes), random_pos=random_positions)

    def __radd__(self, other):
        result = str.__add__(other, self)
        shift_position_taints(self, len(other))
        nodes = set(get_taint_origins(other)) | set(get_taint_origins(self))
        random_positions = get_random_positions(other) + get_random_positions(self)
        return TaintStr(result, taint_origin=list(nodes), random_pos=random_positions)

    def __format__(self, format_spec):
        result = str.__format__(self, format_spec)
        return TaintStr(result, self._taint_origin, self._random_positions)

    def __getitem__(self, key):
        result = str.__getitem__(self, key)
        pos: Position
        updated_positions = []
        for pos in get_random_positions(self):
            if isinstance(key, slice):
                zero_point = 0
                if key.start is not None:
                    if key.start >= 0:
                        zero_point = key.start
                    else:
                        zero_point = max(0, len(self) + key.start)
                indices_key = list(range(0, len(self)))[key]
                overlap = [i for i in range(pos.start, pos.stop) if i in indices_key]
                if overlap != []:
                    updated_positions.append(
                        Position(min(overlap) - zero_point, max(overlap) - zero_point + 1)
                    )
            else:
                # key: int
                if key >= pos.start and key < pos.stop:
                    updated_positions.append(Position(key, key))
        return TaintStr(result, taint_origin=self._taint_origin, random_pos=updated_positions)

    def __mod__(self, other):
        result = str.__mod__(inject_random_marker(self), inject_random_marker(other))
        if result is NotImplemented:
            return NotImplemented
        result, positions = remove_random_marker(result)
        nodes = set(get_taint_origins(self))
        if isinstance(other, (tuple, list)):
            for o in other:
                nodes.update(get_taint_origins(o))
        else:
            nodes.update(get_taint_origins(other))
        return TaintStr(result, list(nodes), random_pos=positions)

    def __rmod__(self, other):
        result = str.__mod__(inject_random_marker(other), inject_random_marker(self))
        if result is NotImplemented:
            return NotImplemented
        result, positions = remove_random_marker(result)
        nodes = set(get_taint_origins(self)) | set(get_taint_origins(other))
        return TaintStr(result, list(nodes), random_pos=positions)

    def encode(self, *args, **kwargs):
        return str(self).encode(*args, **kwargs)

    def decode(self, *args, **kwargs):
        return str(self).decode(*args, **kwargs)

    def join(self, iterable):
        joined = str(self).join([str(x) for x in iterable])
        curr_offs = 0
        random_positions = []
        for value in iterable:
            shift_position_taints(value, curr_offs)
            curr_offs += len(str(value)) + len(str(self))
            random_positions.extend(get_random_positions(value))
        nodes = set(get_taint_origins(self))
        for x in iterable:
            nodes.update(get_taint_origins(x))
        return TaintStr(joined, list(nodes), random_pos=random_positions)

    def __str__(self):
        return str.__str__(self)

    # we don't want to change repr since this can alter behavior e.g.
    # in the case of this: '%r' % some_tainted_str
    def __repr__(self):
        return super().__repr__()

    # this is for debugging
    def taint_repr(self):
        return (
            f"TaintStr({super().__repr__()}, taint_origin={self._taint_origin}"
            f", random_positions={self._random_positions})"
        )

    def get_raw(self):
        return str(self)

    # Add more methods for compatibility
    def upper(self, *args, **kwargs):
        return TaintStr(
            str.upper(self, *args, **kwargs), self._taint_origin, self._random_positions
        )

    def lower(self, *args, **kwargs):
        return TaintStr(
            str.lower(self, *args, **kwargs), self._taint_origin, self._random_positions
        )

    def strip(self, *args, **kwargs):
        marked_self = inject_random_marker_str(self)
        result = str.strip(marked_self, *args, **kwargs)
        result, positions = remove_random_marker(result)
        return TaintStr(result, self._taint_origin, random_pos=positions)

    def lstrip(self, *args, **kwargs):
        marked_self = inject_random_marker_str(self)
        result = str.lstrip(marked_self, *args, **kwargs)
        result, positions = remove_random_marker(result)
        return TaintStr(result, self._taint_origin, random_pos=positions)

    def rstrip(self, *args, **kwargs):
        marked_self = inject_random_marker_str(self)
        result = str.rstrip(marked_self, *args, **kwargs)
        result, positions = remove_random_marker(result)
        return TaintStr(result, self._taint_origin, random_pos=positions)

    def replace(self, old, new, *args, **kwargs):
        marked_self = inject_random_marker(self)
        result = str.replace(
            marked_self, inject_random_marker(old), inject_random_marker(new), *args, **kwargs
        )
        result, positions = remove_random_marker(result)
        nodes = set(get_taint_origins(self)) | set(get_taint_origins(new))
        return TaintStr(result, list(nodes), random_pos=positions)

    def split(self, *args, **kwargs):
        marked_self = inject_random_marker(self, level="char")
        result_split = str.split(marked_self, *args, **kwargs)
        result = []
        for marked_element in result_split:
            element, positions = remove_random_marker(marked_element, level="char")
            result.append(TaintStr(element, taint_origin=self._taint_origin, random_pos=positions))
        return result

    def capitalize(self, *args, **kwargs):
        return TaintStr(
            str.capitalize(self, *args, **kwargs), self._taint_origin, self._random_positions
        )

    def title(self, *args, **kwargs):
        return TaintStr(
            str.title(self, *args, **kwargs), self._taint_origin, self._random_positions
        )

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
        return super().__int__()

    def __float__(self):
        return super().__float__()

    def __index__(self):
        return super().__index__()

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
        return super().__int__()

    def __float__(self):
        return super().__float__()

    def __index__(self):
        return super().__index__()

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


class TaintedCallable:
    """
    Wrapper for callable objects (methods, functions) that taints their return values.
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

    def __call__(self, *args, **kwargs):
        # Call the original callable
        result = self._wrapped(*args, **kwargs)
        # Taint the result
        return taint_wrap(result, taint_origin=self._taint_origin)

    def __getattr__(self, name):
        # Delegate attribute access to the wrapped callable
        return getattr(self._wrapped, name)

    def __repr__(self):
        return f"TaintedCallable({repr(self._wrapped)}, taint_origin={self._taint_origin})"

    def get_raw(self):
        return self._wrapped


# Helper to detect OpenAI SDK objects (Response, Assistant, etc.)
def is_openai_sdk_object(obj):
    """
    Check if an object is from the OpenAI SDK types module.

    This is a more specific check than is_openai_response, looking specifically
    for objects from the openai.types module hierarchy.

    Args:
        obj: The object to check

    Returns:
        True if the object is from openai.types.*, False otherwise
    """
    cls = obj.__class__
    mod = cls.__module__
    # Covers openai.types.responses.response, openai.types.beta.assistant, etc.
    return mod.startswith("openai.types.")


def taint_wrap(obj, taint_origin=None, _seen=None):
    """
    Recursively wrap an object and its nested structures with taint information.

    This function takes any object and wraps it with appropriate tainted versions
    (TaintStr, TaintInt, TaintFloat, etc.) while preserving the original structure.
    It handles nested data structures like lists, dictionaries, and custom objects.

    Args:
        obj: The object to wrap with taint information
        taint_origin: The taint origin(s) to assign to the wrapped object
        _seen: Set to track visited objects (prevents circular references)

    Returns:
        The wrapped object with taint information, or the original object if
        no appropriate tainted wrapper exists
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
    if callable(obj) and not isinstance(obj, type):
        return TaintedCallable(obj, taint_origin=taint_origin)
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


def shift_position_taints(obj: str | TaintStr, offs: int) -> list:
    """
    Shift position taints in an object's random positions by a given offset.

    Args:
        obj: The object to extract and adjust positions from
        offs: The offset to add to position-based taints
    """
    if isinstance(obj, TaintStr) and get_random_positions(obj) != []:
        pos: Position
        for pos in obj._random_positions:
            pos.shift(offs)


def get_random_positions(val: str | TaintStr) -> list:
    """
    Extract random position objects from a TaintStr or regular string.

    Args:
        val: The string or TaintStr to extract random positions from

    Returns:
        List of Position objects representing random position tracking information.
        Returns empty list if val is not a TaintStr or has no random positions.
    """
    if isinstance(val, TaintStr) and val._random_positions is not None:
        return val._random_positions
    else:
        return []


def inject_random_marker(value: list | tuple, level: str = "str") -> list | tuple:
    """
    Inject random markers around tainted positions in strings within a collection.

    This function processes lists, tuples, and individual strings/TaintStr objects,
    adding >> and << markers around random positions to visualize taint tracking.

    Args:
        value: A list, tuple, string, or TaintStr to process
        level: Insert the modifiers at the string or char level. Default is str

    Returns:
        The same type as input with random markers injected around tainted positions
    """
    if isinstance(value, (str, TaintStr)):
        return inject_random_marker_str(value, level=level)
    elif isinstance(value, (list, tuple)):
        injected = [
            (
                inject_random_marker_str(element, level=level)
                if isinstance(element, (str, TaintStr))
                else element
            )
            for element in value
        ]
        return type(value)(injected)
    else:
        return value


def inject_random_marker_str(value: str | TaintStr, level: str = "str") -> str | TaintStr:
    """
    Inject random markers around tainted positions in a single string.

    This function adds >> and << markers around positions tracked by Position objects
    in a TaintStr, making it easier to visualize which parts of the string are tainted.

    Args:
        value: A string or TaintStr to inject markers into
        level: Insert the modifiers at the string or char level. Default is str

    Returns:
        The string with >> and << markers around tainted positions, or the original
        string if no random positions are tracked
    """
    modified_string = []
    if isinstance(value, TaintStr) and get_random_positions(value) != []:
        last_end = 0
        pos: Position
        for pos in value._random_positions:
            modified_string.append(value[last_end : pos.start])
            if level == "str":
                modified_string.append(">>" + value[pos.start : pos.stop] + "<<")
            elif level == "char":
                modified_string.append(
                    "".join([f">>{char}<<" for char in value[pos.start : pos.stop]])
                )
            else:
                raise ValueError(f"Unknown level {level}")
            last_end = pos.stop
        value = TaintStr("").join(modified_string)
    return value


def remove_random_marker(
    val: str | TaintStr, level: str = "str"
) -> tuple[str | TaintStr, list[Position]]:
    """
    This function removes random markers << and >> from the string
    by checking for regex patterns of the form <<str>>. The function
    also finds the positions of the enclosed str's in the new string without
    the markers.
    Example: Hell<<o>> this <<is a>> string -> Hello this is a string, [4,4], [11,15]

    TODO rewrite and args
    """
    input_str = str(val)

    # Find all matches of <<content>>
    if level == "str":
        pattern = r">>([^<>]*)<<"
    elif level == "char":
        input_str = input_str.lstrip("<<")
        input_str = input_str.rstrip(">>")
        pattern = r"((?:>>[^<>]<<)+)"
    else:
        raise ValueError(f"Unknown level {level}")
    matches = list(re.finditer(pattern, input_str))

    if not matches:
        return val, []

    result_parts = []
    positions = []
    last_end = 0

    for match in matches:
        result_parts.append(input_str[last_end : match.start()])
        content = match.group(1)
        current_pos = len("".join(result_parts))
        if level == "char":
            # Handle broken character-level sequences
            # Remove all >> and << markers, then extract remaining characters
            content = re.sub(r">>|<<", "", content)
        result_parts.append(content)
        if content:  # Only create position if there's actual content
            positions.append(Position(current_pos, current_pos + len(content)))
        last_end = match.end()

    result_parts.append(input_str[last_end:])
    result_str = "".join(result_parts)
    return result_str, positions
