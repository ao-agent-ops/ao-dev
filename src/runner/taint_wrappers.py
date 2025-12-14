import io
import inspect
import threading
from typing import Any, Set
from types import ModuleType
from enum import Enum
from aco.server.database_manager import DB
from aco.common.logger import logger


class TaintObject:
    """
    A wrapper for arbitrary objects that tracks taint origins.

    This class wraps objects that don't fit into the basic tainted types
    (TaintStr, TaintInt, TaintFloat, TaintList, TaintDict, etc.).
    The wrapped object remains completely unchanged. All operations unwrap
    taint from arguments, execute on the raw object, and wrap results with
    combined taint information.

    Attributes:
        obj: The wrapped object (never modified)
        _taint_origin (list): List of taint origin identifiers for this wrapper
    """

    def __init__(self, obj, taint_origin=None):
        object.__setattr__(self, "obj", obj)
        if taint_origin is None:
            object.__setattr__(self, "_taint_origin", [])
        elif isinstance(taint_origin, (int, str)):
            object.__setattr__(self, "_taint_origin", [taint_origin])
        elif isinstance(taint_origin, (list, set)):
            object.__setattr__(self, "_taint_origin", list(taint_origin))
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")

    def _unwrap_args(self, *args):
        """Unwrap tainted arguments and collect taint origins."""
        origins = set(object.__getattribute__(self, "_taint_origin"))
        unwrapped = []
        for arg in args:
            origins.update(get_taint_origins(arg))
            unwrapped.append(untaint_if_needed(arg))
        return unwrapped, list(origins)

    def _unwrap_kwargs(self, kwargs):
        """Unwrap tainted kwargs and collect taint origins."""
        origins = set(object.__getattribute__(self, "_taint_origin"))
        unwrapped = {}
        for key, val in kwargs.items():
            origins.update(get_taint_origins(val))
            unwrapped[key] = untaint_if_needed(val)
        return unwrapped, list(origins)

    def bound_method(self, method_name, *args, **kwargs):
        """
        Call a method on the wrapped object with the given arguments.

        This method retrieves the named method from self.obj and calls it with
        the provided arguments. It's used by __getattr__ via functools.partial
        to create bound methods that preserve __self__ = self (TaintObject).

        When exec_func receives a call like obj.method(args), it can extract taint
        from func.__self__ (which is self, the TaintObject) and combine it with
        taint from the arguments.

        Args:
            method_name: The name of the method to call on self.obj
            *args: Positional arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method

        Returns:
            The result of calling the method on self.obj
        """
        obj = object.__getattribute__(self, "obj")
        method = getattr(obj, method_name)
        return method(*args, **kwargs)

    def __getattr__(self, name):
        """Delegate attribute access to wrapped object."""
        if name in ("obj", "_taint_origin"):
            return object.__getattribute__(self, name)
        obj = object.__getattribute__(self, "obj")
        result = getattr(obj, name)

        # If it's callable (a method), return via partial to preserve __self__ = self
        # This allows exec_func to extract taint from the TaintObject
        if callable(result):
            from functools import partial

            return partial(self.bound_method, name)

        # For non-callable attributes, wrap with taint information
        taint_origin = object.__getattribute__(self, "_taint_origin")
        if taint_origin:
            return taint_wrap(result, taint_origin=taint_origin)
        return result

    def __setattr__(self, name, value):
        """Unwrap value and set on wrapped object."""
        if name in ("obj", "_taint_origin"):
            object.__setattr__(self, name, value)
        else:
            obj = object.__getattribute__(self, "obj")
            unwrapped_value = untaint_if_needed(value)
            setattr(obj, name, unwrapped_value)

    def __getitem__(self, key):
        """Get item from wrapped object and wrap result."""
        obj = object.__getattribute__(self, "obj")
        taint_origin = object.__getattribute__(self, "_taint_origin")
        unwrapped_key = untaint_if_needed(key)
        result = obj[unwrapped_key]
        if taint_origin:
            return taint_wrap(result, taint_origin=taint_origin)
        return result

    def __setitem__(self, key, value):
        """Unwrap key and value, set on wrapped object."""
        obj = object.__getattribute__(self, "obj")
        unwrapped_key = untaint_if_needed(key)
        unwrapped_value = untaint_if_needed(value)
        obj[unwrapped_key] = unwrapped_value

    def __delitem__(self, key):
        """Delete item from wrapped object."""
        obj = object.__getattribute__(self, "obj")
        unwrapped_key = untaint_if_needed(key)
        del obj[unwrapped_key]

    def __call__(self, *args, **kwargs):
        """Unwrap args/kwargs, call wrapped object, wrap result."""
        obj = object.__getattribute__(self, "obj")
        unwrapped_args, combined_origins = self._unwrap_args(*args)
        unwrapped_kwargs, kwargs_origins = self._unwrap_kwargs(kwargs)
        combined_origins = list(set(combined_origins) | set(kwargs_origins))

        result = obj(*unwrapped_args, **unwrapped_kwargs)

        if combined_origins:
            return taint_wrap(result, taint_origin=combined_origins)
        return result

    def __repr__(self):
        obj = object.__getattribute__(self, "obj")
        taint_origin = object.__getattribute__(self, "_taint_origin")
        return f"TaintObject({repr(obj)}, taint_origin={taint_origin})"

    def __str__(self):
        obj = object.__getattribute__(self, "obj")
        return str(obj)

    def __bool__(self):
        obj = object.__getattribute__(self, "obj")
        return bool(obj)

    def __len__(self):
        obj = object.__getattribute__(self, "obj")
        return len(obj)

    def __iter__(self):
        obj = object.__getattribute__(self, "obj")
        return iter(obj)

    def __hash__(self):
        obj = object.__getattribute__(self, "obj")
        return hash(obj)

    def __eq__(self, other):
        obj = object.__getattribute__(self, "obj")
        if isinstance(other, TaintObject):
            other = object.__getattribute__(other, "obj")
        return obj == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        obj = object.__getattribute__(self, "obj")
        if isinstance(other, TaintObject):
            other = object.__getattribute__(other, "obj")
        return obj < other

    def __le__(self, other):
        obj = object.__getattribute__(self, "obj")
        if isinstance(other, TaintObject):
            other = object.__getattribute__(other, "obj")
        return obj <= other

    def __gt__(self, other):
        obj = object.__getattribute__(self, "obj")
        if isinstance(other, TaintObject):
            other = object.__getattribute__(other, "obj")
        return obj > other

    def __ge__(self, other):
        obj = object.__getattribute__(self, "obj")
        if isinstance(other, TaintObject):
            other = object.__getattribute__(other, "obj")
        return obj >= other

    def __contains__(self, item):
        obj = object.__getattribute__(self, "obj")
        unwrapped_item = untaint_if_needed(item)
        return unwrapped_item in obj

    def get_raw(self):
        """Return the wrapped object."""
        obj = object.__getattribute__(self, "obj")
        if hasattr(obj, "get_raw"):
            return obj.get_raw()
        return obj

    def __reduce__(self):
        """For pickle/copy operations, return the wrapped object."""
        obj = object.__getattribute__(self, "obj")
        return (lambda x: x, (obj,))

    def __copy__(self):
        """For shallow copy, return wrapped object."""
        obj = object.__getattribute__(self, "obj")
        return obj

    def __deepcopy__(self, memo):
        """For deep copy, return wrapped object."""
        import copy

        obj = object.__getattribute__(self, "obj")
        return copy.deepcopy(obj, memo)

    def __enter__(self):
        """Support context manager protocol by delegating to wrapped object."""
        obj = object.__getattribute__(self, "obj")
        return obj.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support context manager protocol by delegating to wrapped object."""
        obj = object.__getattribute__(self, "obj")
        return obj.__exit__(exc_type, exc_val, exc_tb)

    # Make this object more transparent to type checkers
    @property
    def __class__(self):
        obj = object.__getattribute__(self, "obj")
        return obj.__class__

    @__class__.setter
    def __class__(self, value):
        obj = object.__getattribute__(self, "obj")
        obj.__class__ = value


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

    # Handle TaintObject wrapper - return the wrapped object directly
    if isinstance(val, TaintObject):
        wrapped = object.__getattribute__(val, "obj")
        # Mark wrapped object as seen to prevent it from being re-processed
        _seen.add(id(wrapped))
        if hasattr(wrapped, "get_raw"):
            return wrapped.get_raw()
        return wrapped

    # If object has get_raw method (tainted), use it
    if hasattr(val, "get_raw"):
        raw_val = val.get_raw()
        return untaint_if_needed(raw_val, _seen)

    # Handle nested data structures
    if isinstance(val, dict):
        return {k: untaint_if_needed(v, _seen) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        result = [untaint_if_needed(item, _seen) for item in val]
        return tuple(result) if isinstance(val, tuple) else result
    elif isinstance(val, set):
        return {untaint_if_needed(item, _seen) for item in val}
    elif isinstance(val, Enum):
        return val
    elif isinstance(val, ModuleType):
        return val
    elif isinstance(
        val,
        (
            threading.Lock,
            threading._CRLock,
            threading.Condition,
            threading.Thread,
            threading.Semaphore,
            threading.BoundedSemaphore,
            threading.Event,
            threading.Barrier,
            threading.Timer,
            threading.local,
        ),
    ):
        return val  # Never modify threading primitives
    elif hasattr(val, "__dict__") and not isinstance(val, type):
        untainted = {}  # avoid mods while iterating over same thing
        for attr, value in val.__dict__.items():
            untainted[attr] = untaint_if_needed(value, _seen)
        for attr, value in untainted.items():
            val.__dict__[attr] = value
        return val
    elif hasattr(val, "__slots__"):
        # Handle objects with __slots__ (some objects have __slots__ but no __dict__).
        untainted = {}  # avoid mods while iterating over same thing
        for slot in val.__slots__:
            if hasattr(val, slot):
                untainted[slot] = untaint_if_needed(getattr(val, slot), _seen)
        for slot, value in untainted.items():
            try:
                setattr(val, slot, value)
            except Exception:
                logger.error(f"[TaintWrapper] error untainting {val}")
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
    try:
        # Use object.__getattribute__ to avoid triggering __getattr__ on proxy objects
        taint_origin = object.__getattribute__(obj, "_taint_origin")
        return bool(taint_origin) and bool(get_taint_origins(obj))
    except AttributeError:
        return False


def get_taint_origins(val, _seen=None, _depth=0, _max_depth=100):
    """
    Return a flat list of all taint origins for the input, including nested objects.

    Args:
        val: The value to extract taint origins from
        _seen: Set to track visited objects (prevents circular references)
        _depth: Current recursion depth
        _max_depth: Maximum recursion depth (default: 100)

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
    # Use object.__getattribute__ to avoid triggering __getattr__ on proxy objects
    try:
        taint_origin = object.__getattribute__(val, "_taint_origin")
        if taint_origin is not None:
            if not isinstance(taint_origin, (list, set)):
                taint_origin = [taint_origin]
            return list(taint_origin)
    except AttributeError:
        # Object doesn't have _taint_origin, continue with other checks
        pass

    # Handle nested data structures
    origins = set()

    if isinstance(val, (list, tuple, set)):
        for v in val:
            origins = safe_update_set(origins, get_taint_origins(v, _seen, _depth + 1, _max_depth))
    elif isinstance(val, dict):
        # Create a list of values to avoid dictionary changed size during iteration
        for v in list(val.values()):
            origins = safe_update_set(origins, get_taint_origins(v, _seen, _depth + 1, _max_depth))
    elif isinstance(val, Enum):
        return origins
    elif hasattr(val, "__dict__") and not isinstance(val, type):
        # Handle custom objects with attributes
        # Create a list of items to avoid dictionary changed size during iteration
        for attr_name, attr_val in list(val.__dict__.items()):
            if attr_name.startswith("_"):
                continue
            origins = safe_update_set(
                origins, get_taint_origins(attr_val, _seen, _depth + 1, _max_depth)
            )
    elif hasattr(val, "__slots__"):
        # Handle objects with __slots__
        for slot in val.__slots__:
            try:
                # Use object.__getattribute__ to avoid triggering __getattr__ on proxy objects
                slot_val = object.__getattribute__(val, slot)
                origins = safe_update_set(
                    origins, get_taint_origins(slot_val, _seen, _depth + 1, _max_depth)
                )
            except AttributeError:
                # Slot doesn't exist on this instance, skip it
                continue

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


# Taint-aware str
class TaintStr(str):
    """
    A taint-aware string class that tracks taint origins.

    TaintStr extends the built-in str class to provide taint tracking capabilities,
    allowing security analysis tools to track the flow of potentially sensitive
    or untrusted data through string operations.

    All string operations are overridden to preserve taint information through
    transformations like concatenation, slicing, case changes, formatting, etc.

    Attributes:
        _taint_origin (list): List of taint origin identifiers
    """

    __class__ = str

    def __new__(cls, value, taint_origin=None):
        obj = str.__new__(cls, value)
        if taint_origin is None:
            obj._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            obj._taint_origin = [taint_origin]
        elif isinstance(taint_origin, (list, set)):
            obj._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")
        return obj

    def __add__(self, other):
        result = str.__add__(self, other)
        nodes = set(get_taint_origins(self)) | set(get_taint_origins(other))
        return TaintStr(result, taint_origin=list(nodes))

    def __radd__(self, other):
        result = str.__add__(other, self)
        nodes = set(get_taint_origins(other)) | set(get_taint_origins(self))
        return TaintStr(result, taint_origin=list(nodes))

    def __format__(self, format_spec):
        result = str.__format__(self, format_spec)
        return TaintStr(result, self._taint_origin)

    def __getitem__(self, key):
        result = str.__getitem__(self, key)
        return TaintStr(result, taint_origin=self._taint_origin)

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

    def join(self, iterable):
        joined = self.get_raw().join([x for x in iterable])
        nodes = set(get_taint_origins(self))
        for x in iterable:
            nodes.update(get_taint_origins(x))
        return TaintStr(joined, list(nodes))

    def encode(self, *args, **kwargs):
        return self.get_raw().encode(*args, **kwargs)

    def decode(self, *args, **kwargs):
        return self.get_raw().decode(*args, **kwargs)

    def __str__(self):
        return self

    # we don't want to change repr since this can alter behavior e.g.
    # in the case of this: '%r' % some_tainted_str
    def __repr__(self):
        return self

    def get_raw(self):
        # return str(self)
        return super().__str__()

    # Add more methods for compatibility
    def upper(self, *args, **kwargs):
        return TaintStr(str.upper(self, *args, **kwargs), self._taint_origin)

    def lower(self, *args, **kwargs):
        return TaintStr(str.lower(self, *args, **kwargs), self._taint_origin)

    def strip(self, *args, **kwargs):
        result = str.strip(self, *args, **kwargs)
        return TaintStr(result, self._taint_origin)

    def lstrip(self, *args, **kwargs):
        result = str.lstrip(self, *args, **kwargs)
        return TaintStr(result, self._taint_origin)

    def rstrip(self, *args, **kwargs):
        result = str.rstrip(self, *args, **kwargs)
        return TaintStr(result, self._taint_origin)

    def replace(self, old, new, *args, **kwargs):
        result = str.replace(self, old, new, *args, **kwargs)
        nodes = set(get_taint_origins(self)) | set(get_taint_origins(new))
        return TaintStr(result, list(nodes))

    def split(self, *args, **kwargs):
        result_split = str.split(self, *args, **kwargs)
        result = [TaintStr(el, taint_origin=self._taint_origin) for el in result_split]
        return result

    def capitalize(self, *args, **kwargs):
        return TaintStr(str.capitalize(self, *args, **kwargs), self._taint_origin)

    def title(self, *args, **kwargs):
        return TaintStr(str.title(self, *args, **kwargs), self._taint_origin)

    def center(self, width, fillchar=" "):
        """
        Return a centered string of specified width with taint tracking preserved.

        Args:
            width (int): The total width of the resulting string
            fillchar (str): Character to use for padding (default: space)

        Returns:
            TaintStr: Centered string with preserved taint information and adjusted positions
        """
        result = str.center(self, width, fillchar)
        return TaintStr(result, self._taint_origin)

    def ljust(self, width, fillchar=" "):
        """
        Return a left-justified string of specified width with taint tracking preserved.

        Args:
            width (int): The total width of the resulting string
            fillchar (str): Character to use for padding (default: space)

        Returns:
            TaintStr: Left-justified string with preserved taint information and adjusted positions
        """
        result = str.ljust(self, width, fillchar)
        return TaintStr(result, self._taint_origin)

    def rjust(self, width, fillchar=" "):
        """
        Return a right-justified string of specified width with taint tracking preserved.

        Args:
            width (int): The total width of the resulting string
            fillchar (str): Character to use for padding (default: space)

        Returns:
            TaintStr: Right-justified string with preserved taint information and adjusted positions
        """
        result = str.rjust(self, width, fillchar)
        return TaintStr(result, self._taint_origin)

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
        result = str.zfill(self, width)
        return TaintStr(result, self._taint_origin)

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
        before, separator, after = str.partition(self, sep)

        return (
            TaintStr(before, self._taint_origin),
            TaintStr(separator, self._taint_origin),
            TaintStr(after, self._taint_origin),
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
        before, separator, after = str.rpartition(self, sep)

        return (
            TaintStr(before, self._taint_origin),
            TaintStr(separator, self._taint_origin),
            TaintStr(after, self._taint_origin),
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
        if taint_origin is None:
            self._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            self._taint_origin = [taint_origin]
        elif isinstance(taint_origin, (set, list)):
            self._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")

        # Merge taint origins from all items into the list's taint
        for v in value:
            # Merge existing taint from the item
            self._taint_origin = list(set(self._taint_origin) | set(get_taint_origins(v)))

        # Initialize with original items (don't retaint them)
        list.__init__(self, value)

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

    def __getitem__(self, key):
        item = list.__getitem__(self, key)
        if isinstance(key, slice):
            # For slices, return a new TaintList with the same taint
            return TaintList(item, taint_origin=self._taint_origin)
        else:
            # Return items as-is, preserving their original taint (or lack thereof)
            return item

    def get_raw(self):
        return [x.get_raw() if hasattr(x, "get_raw") else x for x in self]


class TaintIterable:
    """
    A taint-aware wrapper for any iterable type that tracks taint origins.

    This class can wrap lists, tuples, sets, and other iterables while preserving
    their original type behavior and adding taint tracking capabilities.

    Attributes:
        _wrapped: The original iterable object
        _taint_origin (list): List of taint origin identifiers
    """

    def __init__(self, wrapped_iterable, taint_origin=None):
        if taint_origin is None:
            self._taint_origin = []
        elif isinstance(taint_origin, (int, str)):
            self._taint_origin = [taint_origin]
        elif isinstance(taint_origin, (set, list)):
            self._taint_origin = list(taint_origin)
        else:
            raise TypeError(f"Unsupported taint_origin type: {type(taint_origin)}")

        # Taint all items and merge their taint origins
        tainted_items = []
        for v in wrapped_iterable:
            # Merge existing taint from the item
            self._taint_origin = list(set(self._taint_origin) | set(get_taint_origins(v)))
            # Taint the item with the combined taint
            tainted_item = taint_wrap(v, taint_origin=self._taint_origin)
            tainted_items.append(tainted_item)

        # Recreate the original type with tainted items
        original_type = type(wrapped_iterable)
        self._wrapped = original_type(tainted_items)

    def __getitem__(self, key):
        item = self._wrapped[key]
        if isinstance(key, slice):
            # For slices, return a new TaintIterable with the same taint
            return TaintIterable(item, taint_origin=self._taint_origin)
        else:
            # For single items, return the item (should already be tainted)
            return item

    def __iter__(self):
        return iter(self._wrapped)

    def __len__(self):
        return len(self._wrapped)

    def __repr__(self):
        return f"TaintIterable({repr(self._wrapped)}, taint_origin={self._taint_origin})"

    def __str__(self):
        return str(self._wrapped)

    def __bool__(self):
        return bool(self._wrapped)

    def __eq__(self, other):
        if isinstance(other, TaintIterable):
            return self._wrapped == other._wrapped
        return self._wrapped == other

    def __hash__(self):
        return hash(self._wrapped)

    def get_raw(self):
        return type(self._wrapped)(
            x.get_raw() if hasattr(x, "get_raw") else x for x in self._wrapped
        )

    # Delegate attribute access to the wrapped object
    def __getattr__(self, name):
        return getattr(self._wrapped, name)

    # Make this object more transparent to type checkers
    @property
    def __class__(self):
        return self._wrapped.__class__

    @__class__.setter
    def __class__(self, value):
        self._wrapped.__class__ = value


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

    def get_raw(self, _seen=None):
        """
        Get the raw dictionary with all tainted values unwrapped.

        Uses _seen to track visited objects and prevent infinite recursion
        on circular references.
        """
        if _seen is None:
            _seen = set()

        # Check if we've already visited this dict
        dict_id = id(self)
        if dict_id in _seen:
            # Return a placeholder to avoid infinite recursion
            # This will let json.dumps raise its own circular reference error
            return self

        _seen.add(dict_id)

        result = {}
        for k, v in self.items():
            if hasattr(v, "get_raw") and callable(v.get_raw):
                try:
                    result[k] = v.get_raw(_seen) if isinstance(v, TaintDict) else v.get_raw()
                except (RecursionError, ValueError):
                    # If we hit a recursion or circular reference, just return the value as-is
                    # This lets json.dumps handle the error
                    result[k] = v
            else:
                result[k] = v

        return result


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
        elif isinstance(taint_origin, (set, list)):
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
        from aco.common.logger import logger
        import os

        # Read from file with taint tracking

        data = self._file.read(size)
        if isinstance(data, bytes):
            # For binary mode, we return raw bytes but track taint separately
            # You might want to create a TaintBytes class for this
            return data

        # For text mode, check if there's taint from previous sessions
        if hasattr(self._file, "name") and data:
            try:
                # Check line 0 for now (we'd need to track all lines for full read)
                prev_session_id, taint_nodes = DB.get_taint_info(self._file.name, 0)

                if prev_session_id and taint_nodes:
                    # Combine existing taint with file taint - the server will handle cross-session nodes
                    combined_taint = list(set(self._taint_origin + taint_nodes))
                    return TaintStr(data, combined_taint)
            except Exception as e:
                import sys

                print(f"Warning: Could not retrieve taint info in read(): {e}", file=sys.stderr)
                logger.error(f"Exception in taint info retrieval: {e}")

        # Return with default file taint
        return TaintStr(data, self._taint_origin)

    def readline(self, size=-1):
        """Read a line from the file and return tainted data."""
        from aco.common.logger import logger

        # Read line with taint tracking

        line = self._file.readline(size)
        if isinstance(line, bytes):
            return line

        # Check for existing taint from previous sessions
        if hasattr(self._file, "name"):
            try:
                prev_session_id, taint_nodes = DB.get_taint_info(self._file.name, self._line_no)

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
        from aco.common.logger import logger

        # Write data with taint tracking

        # Extract raw data if tainted
        raw_data = untaint_if_needed(data)

        # Store taint information in database if we have a session ID and file name
        if self._session_id and hasattr(self._file, "name"):
            taint_nodes = get_taint_origins(data)
            if taint_nodes:
                # Store taint for the current line being written
                try:
                    DB.store_taint_info(
                        self._session_id, self._file.name, self._line_no, taint_nodes
                    )
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
                        DB.store_taint_info(
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


def taint_wrap(
    obj, taint_origin=None, inplace=False, _seen=None, _depth: int = 0, _max_depth: int = 10
):
    """
    Recursively wrap an object and its nested structures with taint information.

    This function takes any object and wraps it with appropriate tainted versions
    (TaintStr, TaintInt, TaintFloat, etc.) while preserving the original structure.
    It handles nested data structures like lists, dictionaries, and custom objects.

    Args:
        obj: The object to wrap with taint information
        taint_origin: The taint origin(s) to assign to the wrapped object
        inplace: Should the object be modified inplace (if possible)
        _seen: Set to track visited objects (prevents circular references)
        _depth: Keep track of depth to avoid to deep recursion

    Returns:
        The wrapped object with taint information, or the original object if
        no appropriate tainted wrapper exists
    """
    if _depth > _max_depth:
        return obj

    # ID of these objects is the same. If we have a list of the same strings,
    # like ["a", "a"] we would end up tainting only the first element
    # because by the time we encounter the second "a", we will have "seen" it
    # and just return it.
    # Note that this is not true for lists, dicts or any other complex objects
    if isinstance(obj, str):
        return TaintStr(obj, taint_origin=taint_origin)
    if isinstance(obj, bool):
        # Don't wrap booleans, return as-is
        return obj
    if isinstance(obj, int):
        return TaintInt(obj, taint_origin=taint_origin)
    if isinstance(obj, float):
        return TaintFloat(obj, taint_origin=taint_origin)

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

    if isinstance(obj, dict):
        tainted_dict = TaintDict(
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
        if inplace:
            obj.update((k, v) for k, v in tainted_dict.items())
            return obj
        return tainted_dict

    if isinstance(obj, list) and not isinstance(obj, (str, bytes, bytearray)):
        tainted_list = TaintList(
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
        if inplace:
            obj[:] = tainted_list
            return obj
        return tainted_list
    if isinstance(obj, tuple):
        return tuple(
            [
                taint_wrap(
                    x,
                    taint_origin=taint_origin,
                    _seen=_seen,
                    _depth=_depth + 1,
                    _max_depth=_max_depth,
                )
                for x in obj
            ]
        )
    if isinstance(obj, io.IOBase):
        return TaintFile(obj, taint_origin=taint_origin)

    is_builtin = obj.__class__.__module__ == "builtins"
    is_function = inspect.isfunction(obj)
    if is_builtin or is_function:
        return obj

    # For all other objects, wrap them in TaintObject as a fallback
    # This includes:
    # - Objects with __dict__ (custom classes)
    # - Objects with __slots__ (some built-in types)
    # - C extension objects like re.Match that have neither __dict__ nor __slots__
    # TaintObject will handle all of these transparently
    return TaintObject(obj, taint_origin=taint_origin)


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
