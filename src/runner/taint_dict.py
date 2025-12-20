"""
Thread-safe wrapper around WeakKeyDictionary for TAINT_DICT.

This module provides a thread-safe WeakKeyDictionary implementation
that serves as the single source of truth for all taint information.

TAINT_DICT entries have the format:
    {obj_or_wrapper: {"self": [origin_ids], "attr_name": [origin_ids], ...}}

Where:
- "self" stores the object's own taint origins
- Built-in attribute names store attribute-specific taint
- Non-built-in attributes get their own TAINT_DICT entries
"""

import threading
from weakref import WeakKeyDictionary


class ThreadSafeWeakKeyDict:
    """
    Thread-safe wrapper around WeakKeyDictionary for TAINT_DICT.

    Uses RLock to allow nested access (e.g., when add_to_taint_dict_and_return
    recursively processes nested structures).
    """

    def __init__(self):
        self._dict = WeakKeyDictionary()
        self._lock = threading.RLock()

    def __contains__(self, key):
        with self._lock:
            return key in self._dict

    def __getitem__(self, key):
        with self._lock:
            return self._dict[key]

    def __setitem__(self, key, value):
        with self._lock:
            self._dict[key] = value

    def __delitem__(self, key):
        with self._lock:
            del self._dict[key]

    def get(self, key, default=None):
        with self._lock:
            return self._dict.get(key, default)

    def pop(self, key, *args):
        with self._lock:
            return self._dict.pop(key, *args)

    def keys(self):
        with self._lock:
            return list(self._dict.keys())

    def values(self):
        with self._lock:
            return list(self._dict.values())

    def items(self):
        with self._lock:
            return list(self._dict.items())

    def __len__(self):
        with self._lock:
            return len(self._dict)

    def clear(self):
        with self._lock:
            self._dict.clear()
