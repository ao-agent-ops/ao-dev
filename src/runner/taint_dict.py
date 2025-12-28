"""
Thread-safe id-based taint dictionary.

This module provides a thread-safe dictionary for storing taint information
using object ids as keys. The key insight is that by storing a reference
to each object, we prevent garbage collection and can use id(obj) as a
stable key.

Structure: {id(obj): (obj, [origin_ids])}

Where:
- id(obj) is the object's memory address (stable while we hold a reference)
- obj is the actual object (kept alive to prevent id reuse)
- [origin_ids] is the list of taint origin identifiers
"""

import threading


class ThreadSafeTaintDict:
    """
    Thread-safe id-based taint dictionary.

    Uses object ids as keys and stores (obj, taint) tuples.
    Keeping the object reference prevents garbage collection,
    ensuring the id remains stable and unique.
    """

    def __init__(self):
        self._dict = {}  # id(obj) -> (obj, [origins])
        self._lock = threading.RLock()

    def add(self, obj, taint):
        """Add object with taint origins, keeping reference alive."""
        with self._lock:
            obj_id = id(obj)
            self._dict[obj_id] = (obj, list(taint))

    def get_taint(self, obj):
        """Get taint origins for object. Returns [] if not found."""
        with self._lock:
            obj_id = id(obj)
            entry = self._dict.get(obj_id)
            result = list(entry[1]) if entry else []
            return result

    def has_taint(self, obj):
        """Check if object has a taint entry."""
        with self._lock:
            return id(obj) in self._dict

    def clear(self):
        """Clear all taint entries."""
        with self._lock:
            self._dict.clear()

    def __len__(self):
        """Return number of taint entries."""
        with self._lock:
            return len(self._dict)

    def __contains__(self, obj):
        """Check if object has a taint entry (for 'in' operator)."""
        with self._lock:
            return id(obj) in self._dict

    def debug_dump(self, prefix=""):
        """Print all entries for debugging."""
        with self._lock:
            print(f"{prefix}TAINT_DICT has {len(self._dict)} entries:")
            for obj_id, (obj, taint) in self._dict.items():
                print(f"  id={obj_id}, taint={taint}, obj={repr(obj)[:80]}")
