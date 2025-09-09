import ast
import re
import io
import inspect
from typing import Any, Set

from .patch_constants import CPYTHON_MODS


obj_id_to_taint_origin = {}


# Utility functions
def safe_update_set(target_set: Set[Any], obj: Any) -> Set[Any]:
    """
    Safely update a set with items from an iterable, skipping unhashable items.

    This function attempts to add items from an iterable to a target set,
    gracefully handling TypeError exceptions that occur when trying to add
    unhashable items (like AST nodes, complex objects, etc.).

    Args:
        target_set: The set to update with new items
        obj: An iterable containing items to add to the set

    Returns:
        The updated target set

    Note:
        This function modifies the target_set in place and also returns it.
        Unhashable items are silently skipped to prevent crashes during
        taint origin extraction from complex nested objects.
    """
    try:
        target_set.update(set(obj))
    except TypeError:
        # Skip unhashable items like AST nodes, complex objects, etc.
        pass
    return target_set


def erase_random_substring(val):
    """
    Remove random/tainted portions from a tainted string, keeping only clean parts.

    This function processes TaintStr objects that contain position markers indicating
    which portions of the string contain random or sensitive data. It extracts and
    concatenates only the clean (non-random) portions of the string.

    Args:
        val: The value to process. Can be any type, but only TaintStr objects
             with _random_positions attribute will be processed. Other types
             are returned unchanged.

    Returns:
        str: A clean string with random portions removed, or the original value
             if it doesn't contain random position tracking.

    Example:
        >>> tainted = TaintStr("Hello world test", random_pos=[Position(6, 11)])
        >>> erase_random(tainted)
        'Hello  test'

    Note:
        - Automatically sorts positions by start position
        - Positions should be non-overlapping for correct results
        - Invalid positions beyond string bounds may cause errors
    """
    if not hasattr(val, "_random_positions"):
        if hasattr(val, "get_raw"):
            return val.get_raw()
        return val

    # Sort positions by start position to handle unsorted input
    sorted_positions = sorted(val._random_positions, key=lambda pos: pos.start)

    last_end = 0
    raw_string = val.get_raw()
    clean_string = []
    for pos in sorted_positions:
        clean_string.append(raw_string[last_end : pos.start])
        last_end = pos.stop
    clean_string.append(raw_string[last_end:])
    return "".join(clean_string)


def untaint_if_needed(val, erase_random: bool = False, _seen=None):
    """
    Recursively remove taint from objects and nested data structures.

    Args:
        val: The value to untaint
        erase_random: If True, removes random substrings that have been marked
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
        if erase_random:
            raw_val = erase_random_substring(val)  # returns raw string
        else:
            raw_val = val.get_raw()
        return untaint_if_needed(raw_val, erase_random, _seen)

    # Handle nested data structures
    if isinstance(val, dict):
        return {k: untaint_if_needed(v, erase_random, _seen) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        result = [untaint_if_needed(item, erase_random, _seen) for item in val]
        return tuple(result) if isinstance(val, tuple) else result
    elif isinstance(val, set):
        return {untaint_if_needed(item, erase_random, _seen) for item in val}
    elif hasattr(val, "__dict__") and not isinstance(val, type):
        # Handle custom objects with attributes, e.g., (MyObj(a=5, b=1)).
        try:
            new_obj = val.__class__.__new__(val.__class__)
            for attr, value in val.__dict__.items():
                setattr(new_obj, attr, untaint_if_needed(value, erase_random, _seen))
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
                    setattr(new_obj, slot, untaint_if_needed(value, erase_random, _seen))
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


def get_taint_origins(val, _seen=None, _depth=0, _max_depth=100):
    """
    Return a flat list of all taint origins for the input, including nested objects.

    Args:
        val: The value to extract taint origins from
        _seen: Set to track visited objects (prevents circular references)
        _depth: Current recursion depth
        _max_depth: Maximum recursion depth (default: 10)

    Returns:
        List of taint origins found in the value and its nested structures
    """
    if _depth > _max_depth:
        return []

    if _seen is None:
        _seen = set()

    obj_id = id(val)
    if obj_id in _seen:
        return []
    _seen.add(obj_id)

    # Check if object has direct taint
    if hasattr(val, "_taint_origin") and val._taint_origin is not None:
        if not isinstance(val._taint_origin, (list, set)):
            val._taint_origin = [val._taint_origin]
        return list(val._taint_origin)

    # Handle nested data structures
    origins = set()

    if isinstance(val, (list, tuple, set)):
        for v in val:
            # origins.update(set(get_taint_origins(v, _seen, _depth + 1, _max_depth)))
            origins = safe_update_set(origins, get_taint_origins(v, _seen, _depth + 1, _max_depth))
    elif isinstance(val, dict):
        for v in val.values():
            # origins.update(set(get_taint_origins(v, _seen, _depth + 1, _max_depth)))
            origins = safe_update_set(origins, get_taint_origins(v, _seen, _depth + 1, _max_depth))
    elif hasattr(val, "__dict__") and not isinstance(val, type):
        # Handle custom objects with attributes
        for attr_name, attr_val in val.__dict__.items():
            if attr_name.startswith("_"):
                continue
            # origins.update(set(get_taint_origins(attr_val, _seen, _depth + 1, _max_depth)))
            origins = safe_update_set(
                origins, get_taint_origins(attr_val, _seen, _depth + 1, _max_depth)
            )
    elif hasattr(val, "__slots__"):
        # Handle objects with __slots__
        for slot in val.__slots__:
            if hasattr(val, slot):
                slot_val = getattr(val, slot)
                origins = safe_update_set(
                    origins, get_taint_origins(slot_val, _seen, _depth + 1, _max_depth)
                )
                # origins.update(set(get_taint_origins(slot_val, _seen, _depth + 1, _max_depth)))

    # this is an object that doesn't have __dict__ or __slots__ so
    # probably a CPython object w/o __dict__ such as re.Match()
    if obj_id in obj_id_to_taint_origin:
        origins = safe_update_set(origins, set(obj_id_to_taint_origin[obj_id]))
        # origins.update(set(obj_id_to_taint_origin[obj_id]))

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
    """
    Represents a position range within a string for tracking tainted/random data.

    This class tracks start and stop positions within strings to mark ranges
    that contain sensitive, random, or tainted data. Used by TaintStr to maintain
    position information through string operations.

    Attributes:
        start (int): The starting position (inclusive) of the range
        stop (int): The ending position (exclusive) of the range
    """

    def __init__(self, start: int, stop: int):
        self.start = start
        self.stop = stop

    def shift(self, offset: int):
        """
        Shift both start and stop positions by the given offset.

        Args:
            offset (int): The amount to shift positions by
        """
        self.start += offset
        self.stop += offset

    def set_pos(self, new_pos: list | tuple):
        """
        Set new start and stop positions from a list or tuple.

        Args:
            new_pos (list | tuple): Two-element sequence containing [start, stop] positions

        Raises:
            AssertionError: If new_pos doesn't have exactly 2 elements or positions are invalid
        """
        assert len(new_pos) == 2, "length of pos must be 2"
        assert new_pos[0] <= new_pos[1], "pos must be increasing"
        self.start, self.stop = new_pos

    def __repr__(self):
        return f"{self.start}:{self.stop}"


# Taint-aware str
class TaintStr(str):
    """
    A taint-aware string class that tracks taint origins and random positions.

    TaintStr extends the built-in str class to provide taint tracking capabilities,
    allowing security analysis tools to track the flow of potentially sensitive
    or untrusted data through string operations.

    The class maintains two types of tracking information:
    1. _taint_origin: A list of taint origins that mark where the data came from
    2. _random_positions: A list of Position objects tracking ranges of characters
                         that contain random or sensitive data

    All string operations are overridden to preserve taint information through
    transformations like concatenation, slicing, case changes, formatting, etc.

    Attributes:
        _taint_origin (list): List of taint origin identifiers
        _random_positions (list): List of Position objects marking tainted ranges
    """

    __class__ = str

    def __new__(cls, value, taint_origin=None, random_pos=None):
        obj = str.__new__(cls, value)
        if taint_origin is None:
            obj._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            obj._taint_origin = [taint_origin]
        elif isinstance(taint_origin, (list, set)):
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
                    updated_positions.append(Position(0, 1))
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
        return self.get_raw().encode(*args, **kwargs)

    def decode(self, *args, **kwargs):
        return self.get_raw().decode(*args, **kwargs)

    def __str__(self):
        # return str.__str__(self)
        return self

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
        # return str(self)
        return super().__str__()

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

    def center(self, width, fillchar=" "):
        """
        Return a centered string of specified width with taint tracking preserved.

        Args:
            width (int): The total width of the resulting string
            fillchar (str): Character to use for padding (default: space)

        Returns:
            TaintStr: Centered string with preserved taint information and adjusted positions
        """
        marked_self = inject_random_marker_str(self)
        add_chars = len(marked_self) - len(self)
        result = str.center(marked_self, width + add_chars, fillchar)
        result, positions = remove_random_marker(result)
        return TaintStr(result, self._taint_origin, random_pos=positions)

    def ljust(self, width, fillchar=" "):
        """
        Return a left-justified string of specified width with taint tracking preserved.

        Args:
            width (int): The total width of the resulting string
            fillchar (str): Character to use for padding (default: space)

        Returns:
            TaintStr: Left-justified string with preserved taint information and adjusted positions
        """
        marked_self = inject_random_marker_str(self)
        add_chars = len(marked_self) - len(self)
        result = str.ljust(marked_self, width + add_chars, fillchar)
        result, positions = remove_random_marker(result)
        return TaintStr(result, self._taint_origin, random_pos=positions)

    def rjust(self, width, fillchar=" "):
        """
        Return a right-justified string of specified width with taint tracking preserved.

        Args:
            width (int): The total width of the resulting string
            fillchar (str): Character to use for padding (default: space)

        Returns:
            TaintStr: Right-justified string with preserved taint information and adjusted positions
        """
        marked_self = inject_random_marker_str(self)
        add_chars = len(marked_self) - len(self)
        result = str.rjust(marked_self, width + add_chars, fillchar)
        result, positions = remove_random_marker(result)
        return TaintStr(result, self._taint_origin, random_pos=positions)

    def zfill(self, width):
        """
        Return a zero-padded numeric string of specified width with taint tracking preserved.

        Pads the string with zeros on the left to fill the specified width.
        For signed strings, the sign is placed before the zeros.

        Args:
            width (int): The total width of the resulting string

        Returns:
            TaintStr: Zero-padded string with preserved taint information and adjusted positions
        """
        marked_self = inject_random_marker_str(self)
        add_chars = len(marked_self) - len(self)
        result = str.zfill(marked_self, width + add_chars)
        result, positions = remove_random_marker(result)
        return TaintStr(result, self._taint_origin, random_pos=positions)

    def partition(self, sep):
        """
        Partition the string at the first occurrence of the separator with taint tracking preserved.

        Splits the string into three parts: the part before the separator, the separator
        itself, and the part after the separator. If the separator is not found, returns
        the original string, an empty separator, and an empty string.

        Args:
            sep (str): The separator string to search for

        Returns:
            tuple: Three-element tuple (before, separator, after) where before and after
                   are TaintStr objects with preserved taint information, and separator
                   is a regular string
        """
        marked_self = inject_random_marker(self, level="char")
        before, separator, after = str.partition(marked_self, inject_random_marker(sep))

        # Process each part
        before, before_positions = remove_random_marker(before, level="char")
        after, after_positions = remove_random_marker(after, level="char")

        return (
            TaintStr(before, self._taint_origin, random_pos=before_positions),
            separator,
            TaintStr(after, self._taint_origin, random_pos=after_positions),
        )

    def rpartition(self, sep):
        """
        Partition the string at the last occurrence of the separator with taint tracking preserved.

        Splits the string into three parts: the part before the separator, the separator
        itself, and the part after the separator. If the separator is not found, returns
        an empty string, an empty separator, and the original string.

        Args:
            sep (str): The separator string to search for

        Returns:
            tuple: Three-element tuple (before, separator, after) where before and after
                   are TaintStr objects with preserved taint information, and separator
                   is a regular string
        """
        marked_self = inject_random_marker(self, level="char")
        before, separator, after = str.rpartition(marked_self, inject_random_marker(sep))

        # Process each part
        before, before_positions = remove_random_marker(before, level="char")
        after, after_positions = remove_random_marker(after, level="char")

        return (
            TaintStr(before, self._taint_origin, random_pos=before_positions),
            separator,
            TaintStr(after, self._taint_origin, random_pos=after_positions),
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
    """
    A taint-aware integer class that tracks taint origins through arithmetic operations.

    TaintInt extends the built-in int class to provide taint tracking capabilities,
    allowing security analysis tools to track the flow of potentially sensitive
    or untrusted data through integer arithmetic operations.

    The class maintains taint origin information and propagates it through
    all arithmetic operations like addition, multiplication, bitwise operations, etc.

    Attributes:
        _taint_origin (list): List of taint origin identifiers
    """

    def __new__(cls, value, taint_origin=None):
        obj = int.__new__(cls, value)
        if taint_origin is None:
            obj._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            obj._taint_origin = [taint_origin]
        elif isinstance(taint_origin, (set, list)):
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
        result = int.__rsub__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __mul__(self, other):
        result = int.__mul__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rmul__(self, other):
        result = int.__rmul__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __floordiv__(self, other):
        result = int.__floordiv__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rfloordiv__(self, other):
        result = int.__rfloordiv__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __truediv__(self, other):
        result = int.__truediv__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintFloat(result, self._propagate_taint(other))

    def __rtruediv__(self, other):
        result = int.__rtruediv__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintFloat(result, self._propagate_taint(other))

    def __mod__(self, other):
        result = int.__mod__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rmod__(self, other):
        result = int.__rmod__(self, other)
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
            int.__rpow__(self, other, modulo) if modulo is not None else int.__pow__(other, self)
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
        result = int.__rand__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __or__(self, other):
        result = int.__or__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __ror__(self, other):
        result = int.__ror__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __xor__(self, other):
        result = int.__xor__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rxor__(self, other):
        result = int.__rxor__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __lshift__(self, other):
        result = int.__lshift__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rlshift__(self, other):
        result = int.__rlshift__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rshift__(self, other):
        result = int.__rshift__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rrshift__(self, other):
        result = int.__rrshift__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __matmul__(self, other):
        result = int.__matmul__(self, other)
        if result is NotImplemented:
            return NotImplemented
        return TaintInt(result, self._propagate_taint(other))

    def __rmatmul__(self, other):
        result = int.__rmatmul__(self, other)
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

    def __hash__(self):
        return super().__hash__()


class TaintFloat(float):
    """
    A taint-aware float class that tracks taint origins through arithmetic operations.

    TaintFloat extends the built-in float class to provide taint tracking capabilities,
    allowing security analysis tools to track the flow of potentially sensitive
    or untrusted data through floating-point arithmetic operations.

    The class maintains taint origin information and propagates it through
    all arithmetic operations like addition, multiplication, division, etc.

    Attributes:
        _taint_origin (list): List of taint origin identifiers
    """

    def __new__(cls, value, taint_origin=None):
        obj = float.__new__(cls, value)
        if taint_origin is None:
            obj._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            obj._taint_origin = [taint_origin]
        elif isinstance(taint_origin, (set, list)):
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
        result = float.__radd__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __sub__(self, other):
        result = float.__sub__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __rsub__(self, other):
        result = float.__rsub__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __mul__(self, other):
        result = float.__mul__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __rmul__(self, other):
        result = float.__rmul__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __floordiv__(self, other):
        result = float.__floordiv__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __rfloordiv__(self, other):
        result = float.__rfloordiv__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __truediv__(self, other):
        result = float.__truediv__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __rtruediv__(self, other):
        result = float.__rtruediv__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __mod__(self, other):
        result = float.__mod__(self, other)
        return TaintFloat(result, self._propagate_taint(other))

    def __rmod__(self, other):
        result = float.__rmod__(self, other)
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
    """
    A taint-aware list class that tracks taint origins through list operations.

    TaintList extends the built-in list class to provide taint tracking capabilities,
    allowing security analysis tools to track the flow of potentially sensitive
    or untrusted data through list operations like append, extend, insert, etc.

    The class maintains taint origin information from both the list itself and
    all items contained within it. When items are added or removed, the taint
    information is automatically updated.

    Attributes:
        _taint_origin (list): List of taint origin identifiers from the list and its items
    """

    def __init__(self, value, taint_origin=None):
        list.__init__(self, value)
        if taint_origin is None:
            self._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            self._taint_origin = [taint_origin]
        elif isinstance(taint_origin, (set, list)):
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
    """
    A taint-aware dictionary class that tracks taint origins through dict operations.

    TaintDict extends the built-in dict class to provide taint tracking capabilities,
    allowing security analysis tools to track the flow of potentially sensitive
    or untrusted data through dictionary operations like setitem, update, pop, etc.

    The class maintains taint origin information from both the dictionary itself and
    all values contained within it. When items are added or removed, the taint
    information is automatically updated.

    Attributes:
        _taint_origin (list): List of taint origin identifiers from the dict and its values
    """

    def __init__(self, value, taint_origin=None):
        dict.__init__(self, value)
        if taint_origin is None:
            self._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            self._taint_origin = [taint_origin]
        elif isinstance(taint_origin, (set, list)):
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
        elif isinstance(taint_origin, (set, list)):
            self._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")

    def __getattr__(self, name):
        value = getattr(self._wrapped, name)
        if self._taint_origin:
            wrapped_value = taint_wrap(value, taint_origin=self._taint_origin)
            return wrapped_value
        return value

    def __getitem__(self, key):
        value = self._wrapped[key]
        if self._taint_origin:
            return taint_wrap(value, taint_origin=self._taint_origin)
        return value

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


class TaintFile:
    """
    A file-like object that preserves taint information during file operations.

    This class wraps a regular file object and ensures that any data read from
    the file is tainted with the specified origin, and any tainted data written
    to the file preserves its taint information for future reads.
    """

    def __init__(self, file_obj, mode="r", taint_origin=None, session_id=None):
        """
        Initialize a TaintFile wrapper.

        Args:
            file_obj: The underlying file object to wrap
            mode: The file mode ('r', 'w', 'a', 'rb', 'wb', etc.)
            taint_origin: The taint origin to apply to data read from this file
            session_id: The current session ID for tracking taint across sessions
        """
        self._file = file_obj
        self._mode = mode
        self._closed = False
        self._line_no = 0  # Track current line number
        self._session_id = session_id or self._get_current_session_id()

        # Set taint origin
        if taint_origin is None:
            # Use the file name as default taint origin if available
            if hasattr(file_obj, "name"):
                self._taint_origin = [f"file:{file_obj.name}"]
            else:
                self._taint_origin = ["file:unknown"]
        elif isinstance(taint_origin, (int, str)):
            self._taint_origin = [taint_origin]
        elif isinstance(taint_origin, list):
            self._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")

    def _get_current_session_id(self):
        """Get the current session ID from environment or context"""
        import os

        return os.environ.get("AGENT_COPILOT_SESSION_ID", None)

    @classmethod
    def open(cls, filename, mode="r", taint_origin=None, session_id=None, **kwargs):
        """
        Open a file with taint tracking.

        Args:
            filename: Path to the file
            mode: File mode
            taint_origin: Taint origin for the file (defaults to filename)
            session_id: The session ID for cross-session tracking
            **kwargs: Additional arguments to pass to open()

        Returns:
            TaintFile object
        """
        file_obj = open(filename, mode, **kwargs)
        if taint_origin is None:
            taint_origin = f"file:{filename}"
        return cls(file_obj, mode, taint_origin, session_id)

    def read(self, size=-1):
        """Read from the file and return tainted data."""
        from common.logger import logger
        import os

        logger.info(
            f"TaintFile.read called for {getattr(self._file, 'name', 'unknown')}, session_id={self._session_id}"
        )
        logger.info(f"Current environment session: {os.environ.get('AGENT_COPILOT_SESSION_ID')}")

        data = self._file.read(size)
        if isinstance(data, bytes):
            # For binary mode, we return raw bytes but track taint separately
            # You might want to create a TaintBytes class for this
            return data

        # For text mode, check if there's taint from previous sessions
        if hasattr(self._file, "name") and data:
            try:
                from server.db import get_taint_info

                # Check line 0 for now (we'd need to track all lines for full read)
                logger.info(f"Checking for taint in read(): file={self._file.name}")
                prev_session_id, taint_nodes = get_taint_info(self._file.name, 0)
                logger.info(
                    f"Retrieved taint in read(): prev_session={prev_session_id}, nodes={taint_nodes}"
                )

                if prev_session_id and taint_nodes:
                    logger.info(
                        f"Found taint from previous session {prev_session_id}: {taint_nodes}"
                    )
                    # Combine existing taint with file taint - the server will handle cross-session nodes
                    combined_taint = list(set(self._taint_origin + taint_nodes))
                    logger.info(f"Returning TaintStr with combined taint: {combined_taint}")
                    return TaintStr(data, combined_taint)
            except Exception as e:
                import sys

                print(f"Warning: Could not retrieve taint info in read(): {e}", file=sys.stderr)
                logger.error(f"Exception in taint info retrieval: {e}")
        else:
            logger.info(
                f"Skipping taint check - file has name: {hasattr(self._file, 'name')}, data length: {len(data) if data else 0}"
            )

        logger.info(f"Returning TaintStr with default taint: {self._taint_origin}")
        return TaintStr(data, self._taint_origin)

    def readline(self, size=-1):
        """Read a line from the file and return tainted data."""
        from common.logger import logger

        logger.debug(
            f"TaintFile.readline called for line {self._line_no} of {getattr(self._file, 'name', 'unknown')}"
        )

        line = self._file.readline(size)
        if isinstance(line, bytes):
            return line

        # Check for existing taint from previous sessions
        if hasattr(self._file, "name"):
            try:
                from server.db import get_taint_info

                logger.debug(f"Checking for taint: file={self._file.name}, line={self._line_no}")
                prev_session_id, taint_nodes = get_taint_info(self._file.name, self._line_no)
                logger.debug(
                    f"Retrieved taint: prev_session={prev_session_id}, nodes={taint_nodes}"
                )

                if prev_session_id and taint_nodes:
                    # Combine existing taint with file taint - the server will handle cross-session nodes
                    combined_taint = list(set(self._taint_origin + taint_nodes))
                    self._line_no += 1
                    return TaintStr(line, combined_taint)
            except Exception as e:
                # Log but don't fail the read operation
                import sys

                print(f"Warning: Could not retrieve taint info: {e}", file=sys.stderr)

        self._line_no += 1
        return TaintStr(line, self._taint_origin)

    def readlines(self, hint=-1):
        """Read lines from the file and return tainted data."""
        lines = self._file.readlines(hint)
        if lines and isinstance(lines[0], bytes):
            return lines
        return [TaintStr(line, self._taint_origin) for line in lines]

    def write(self, data):
        """
        Write data to the file.

        If the data is tainted, the taint information is preserved
        and stored in the database for cross-session tracking.
        """
        from common.logger import logger

        logger.debug(
            f"TaintFile.write called for {getattr(self._file, 'name', 'unknown')}, session_id={self._session_id}"
        )

        # Extract raw data if tainted
        raw_data = untaint_if_needed(data)

        # Store taint information in database if we have a session ID and file name
        if self._session_id and hasattr(self._file, "name"):
            taint_nodes = get_taint_origins(data)
            logger.debug(f"Writing with taint nodes: {taint_nodes}")
            if taint_nodes:
                # Store taint for the current line being written
                try:
                    from server.db import store_taint_info

                    store_taint_info(self._session_id, self._file.name, self._line_no, taint_nodes)
                except Exception as e:
                    # Log but don't fail the write operation
                    import sys

                    print(f"Warning: Could not store taint info: {e}", file=sys.stderr)

                # Increment line number for each newline in the data
                newline_count = raw_data.count("\n") if isinstance(raw_data, str) else 0
                self._line_no += max(1, newline_count)

        return self._file.write(raw_data)

    def writelines(self, lines):
        """Write multiple lines to the file."""
        raw_lines = []
        for line in lines:
            # Store taint for each line
            if self._session_id and hasattr(self._file, "name"):
                taint_nodes = get_taint_origins(line)
                if taint_nodes:
                    try:
                        from server.db import store_taint_info

                        store_taint_info(
                            self._session_id, self._file.name, self._line_no, taint_nodes
                        )
                    except Exception as e:
                        import sys

                        print(f"Warning: Could not store taint info: {e}", file=sys.stderr)
            self._line_no += 1
            raw_lines.append(untaint_if_needed(line))
        return self._file.writelines(raw_lines)

    def __iter__(self):
        """Iterate over lines in the file, returning tainted strings."""
        return self

    def __next__(self):
        """Get next line for iteration."""
        line = self._file.__next__()
        if isinstance(line, bytes):
            return line
        return TaintStr(line, self._taint_origin)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def close(self):
        """Close the underlying file."""
        if not self._closed:
            self._file.close()
            self._closed = True

    def flush(self):
        """Flush the file buffer."""
        return self._file.flush()

    def seek(self, offset, whence=0):
        """Seek to a position in the file."""
        return self._file.seek(offset, whence)

    def tell(self):
        """Get current file position."""
        return self._file.tell()

    def fileno(self):
        """Get the file descriptor."""
        return self._file.fileno()

    def isatty(self):
        """Check if the file is a TTY."""
        return self._file.isatty()

    def truncate(self, size=None):
        """Truncate the file."""
        return self._file.truncate(size)

    @property
    def closed(self):
        """Check if the file is closed."""
        return self._closed

    @property
    def mode(self):
        """Get the file mode."""
        return self._mode

    @property
    def name(self):
        """Get the file name."""
        return getattr(self._file, "name", None)

    @property
    def encoding(self):
        """Get the file encoding."""
        return getattr(self._file, "encoding", None)

    @property
    def errors(self):
        """Get the error handling mode."""
        return getattr(self._file, "errors", None)

    @property
    def newlines(self):
        """Get the newlines mode."""
        return getattr(self._file, "newlines", None)

    def readable(self):
        """Check if the file is readable."""
        return self._file.readable()

    def writable(self):
        """Check if the file is writable."""
        return self._file.writable()

    def seekable(self):
        """Check if the file is seekable."""
        return self._file.seekable()

    def __repr__(self):
        """String representation."""
        return f"TaintFile({self._file!r}, taint_origin={self._taint_origin})"


def open_with_taint(filename, mode="r", taint_origin=None, session_id=None, **kwargs):
    """
    Convenience function to open a file with taint tracking.

    Usage:
        with open_with_taint('data.txt', taint_origin='user_input') as f:
            content = f.read()  # content will be a TaintStr

    Args:
        filename: Path to the file
        mode: File mode
        taint_origin: Taint origin for the file
        session_id: The session ID for cross-session tracking
        **kwargs: Additional arguments to pass to open()

    Returns:
        TaintFile object
    """
    return TaintFile.open(filename, mode, taint_origin, session_id, **kwargs)


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


def taint_wrap(obj, taint_origin=None, _seen=None, _depth: int = 0, _max_depth: int = 10):
    """
    Recursively wrap an object and its nested structures with taint information.

    This function takes any object and wraps it with appropriate tainted versions
    (TaintStr, TaintInt, TaintFloat, etc.) while preserving the original structure.
    It handles nested data structures like lists, dictionaries, and custom objects.

    Args:
        obj: The object to wrap with taint information
        taint_origin: The taint origin(s) to assign to the wrapped object
        _seen: Set to track visited objects (prevents circular references)
        _depth: Keep track of depth to avoid to deep recursion

    Returns:
        The wrapped object with taint information, or the original object if
        no appropriate tainted wrapper exists
    """
    if _depth > _max_depth:
        return obj

    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if obj_id in _seen:
        return obj
    _seen.add(obj_id)

    if is_tainted(obj):
        return obj
    if hasattr(obj, "__class__") and hasattr(obj.__class__, "__mro__"):
        import enum

        if issubclass(obj.__class__, enum.Enum):
            return obj  # Don't wrap any enum members (including StrEnum)
    if isinstance(obj, str):
        obj, random_pos = remove_random_marker(obj, level="str")
        return TaintStr(obj, taint_origin=taint_origin, random_pos=random_pos)
    if isinstance(obj, bool):
        # Don't wrap booleans, return as-is
        return obj
    if isinstance(obj, int):
        return TaintInt(obj, taint_origin=taint_origin)
    if isinstance(obj, float):
        return TaintFloat(obj, taint_origin=taint_origin)
    if is_openai_sdk_object(obj):
        return TaintedOpenAIObject(obj, taint_origin=taint_origin)
    if isinstance(obj, dict):
        return TaintDict(
            {
                taint_wrap(
                    k,
                    taint_origin=taint_origin,
                    _seen=_seen,
                    _depth=_depth + 1,
                    _max_depth=_max_depth,
                ): taint_wrap(
                    v,
                    taint_origin=taint_origin,
                    _seen=_seen,
                    _depth=_depth + 1,
                    _max_depth=_max_depth,
                )
                for k, v in obj.items()
            },
            taint_origin=taint_origin,
        )
    if isinstance(obj, list) and not isinstance(obj, (str, bytes, bytearray)):
        return TaintList(
            [
                taint_wrap(
                    x,
                    taint_origin=taint_origin,
                    _seen=_seen,
                    _depth=_depth + 1,
                    _max_depth=_max_depth,
                )
                for x in obj
            ],
            taint_origin=taint_origin,
        )
    if isinstance(obj, io.IOBase):
        return TaintFile(obj, taint_origin=taint_origin)
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        for attr in list(vars(obj)):
            if attr.startswith("_"):
                continue
            try:
                setattr(
                    obj,
                    attr,
                    taint_wrap(
                        getattr(obj, attr),
                        taint_origin=taint_origin,
                        _seen=_seen,
                        _depth=_depth + 1,
                        _max_depth=_max_depth,
                    ),
                )
            except Exception:
                pass
        return obj
    if hasattr(obj, "__slots__"):
        for slot in obj.__slots__:
            try:
                val = getattr(obj, slot)
                setattr(
                    obj,
                    slot,
                    taint_wrap(
                        val,
                        taint_origin=taint_origin,
                        _seen=_seen,
                        _depth=_depth + 1,
                        _max_depth=_max_depth,
                    ),
                )
            except Exception:
                pass
        return obj

    is_builtin = obj.__class__.__module__ == "builtins"
    is_function = inspect.isfunction(obj)
    if is_builtin or is_function:
        return obj

    is_cpython_mod = obj.__class__.__module__ in CPYTHON_MODS
    if is_cpython_mod:
        # Probably a CPython object w/o __dict__
        if obj_id in obj_id_to_taint_origin:
            obj_id_to_taint_origin[obj_id].update(set(taint_origin))
        else:
            obj_id_to_taint_origin[obj_id] = set(taint_origin)
        return obj
    # what obj is here?
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


def inject_random_marker(
    value, level: str = "str", _seen=None, _depth: int = 0, _max_depth: int = 100
):
    """
    Recursively inject random markers around tainted positions in any object.

    This function processes any object and injects >> and << markers around random
    positions in TaintStr objects that have position tracking. The object structure
    is preserved and returned in the same form as the input.

    Args:
        value: Any object to process for marker injection
        level: Insert the modifiers at the string or char level. Default is str
        _seen: Set to track visited objects (prevents circular references)
        _depth: Current recursion depth
        _max_depth: Maximum recursion depth

    Returns:
        The same type as input with random markers injected around tainted positions
    """
    if _depth > _max_depth:
        return value

    if _seen is None:
        _seen = set()

    # Handle TaintStr with positions - this is the core case
    # Don't use circular reference protection for TaintStr as they convert to regular strings
    if isinstance(value, TaintStr) and get_random_positions(value):
        return inject_random_marker_str(value, level=level)
    # Handle regular strings - no markers needed
    elif isinstance(value, str):
        return value

    # For complex objects, use circular reference protection
    obj_id = id(value)
    if obj_id in _seen:
        return value
    _seen.add(obj_id)

    # Handle lists and tuples
    if isinstance(value, (list, tuple)):
        injected = [
            inject_random_marker(
                element, level=level, _seen=_seen, _depth=_depth + 1, _max_depth=_max_depth
            )
            for element in value
        ]
        return type(value)(injected)
    # Handle dictionaries
    if isinstance(value, dict):
        injected = {
            k: inject_random_marker(
                v, level=level, _seen=_seen, _depth=_depth + 1, _max_depth=_max_depth
            )
            for k, v in value.items()
        }
        return type(value)(injected)
    # Handle sets
    if isinstance(value, set):
        injected = {
            inject_random_marker(
                item, level=level, _seen=_seen, _depth=_depth + 1, _max_depth=_max_depth
            )
            for item in value
        }
        return injected
    # Handle custom objects with __dict__
    if hasattr(value, "__dict__") and not isinstance(value, type):
        # Create a copy to avoid modifying the original
        try:
            new_obj = value.__class__.__new__(value.__class__)
            for attr, attr_val in value.__dict__.items():
                setattr(
                    new_obj,
                    attr,
                    inject_random_marker(
                        attr_val, level=level, _seen=_seen, _depth=_depth + 1, _max_depth=_max_depth
                    ),
                )
            return new_obj
        except Exception:
            # If we can't copy, return original
            return value
    # Handle objects with __slots__
    if hasattr(value, "__slots__"):
        try:
            new_obj = value.__class__.__new__(value.__class__)
            for slot in value.__slots__:
                if hasattr(value, slot):
                    slot_val = getattr(value, slot)
                    setattr(
                        new_obj,
                        slot,
                        inject_random_marker(
                            slot_val,
                            level=level,
                            _seen=_seen,
                            _depth=_depth + 1,
                            _max_depth=_max_depth,
                        ),
                    )
            return new_obj
        except Exception:
            return value
    # For all other types (primitives, functions, etc.), return as-is
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
            modified_string.append(value[last_end : pos.start].get_raw())
            if level == "str":
                modified_string.append(">>" + value[pos.start : pos.stop].get_raw() + "<<")
            elif level == "char":
                modified_string.append(
                    "".join([f">>{char}<<" for char in value[pos.start : pos.stop].get_raw()])
                )
            else:
                raise ValueError(f"Unknown level {level}")
            last_end = pos.stop
        modified_string.append(value[last_end : len(value)].get_raw())
        value = "".join(modified_string)
    return value


def remove_random_marker(
    val: str | TaintStr, level: str = "str"
) -> tuple[str | TaintStr, list[Position]]:
    """
    Remove random markers from a string and extract position information.

    This function removes >> and << markers that were inserted by inject_random_marker
    functions and returns both the clean string and Position objects representing
    where the marked content was located in the cleaned string.

    Args:
        val (str | TaintStr): The string containing random markers to remove
        level (str): The marker level to process - "str" for >>content<< markers,
                     "char" for character-level >>c<< markers. Default is "str"

    Returns:
        tuple[str | TaintStr, list[Position]]: A tuple containing:
            - The cleaned string with markers removed
            - List of Position objects indicating where marked content is located

    Example:
        >>> remove_random_marker("Hell>>o<< this >>is a<< string")
        ('Hello this is a string', [Position(4, 5), Position(11, 15)])
    """
    if isinstance(val, TaintStr):
        input_str = val.get_raw()
    else:
        input_str = val

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
