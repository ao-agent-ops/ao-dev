"""
Thread-safe taint tracking: id-based dictionary and context-aware stack.

This module provides:
1. ThreadSafeTaintDict: Tracks taint on specific Python objects using id(obj)
2. TaintStack: Stack-based taint context for passing taint through third-party code

TAINT_DICT: {id(obj): (obj, [origin_ids])}
- Used when we can track specific objects through user code
- Keeps object references to prevent garbage collection

TAINT_STACK: Stack of taint contexts (tuple of tuples)
- Used when third-party code creates new objects we can't track
- exec_func pushes/pops contexts, patches read/update the top
- Union semantics ensure nested calls inherit outer taint

Why task-keyed storage instead of ContextVar:
- LangChain uses copy_context().run() which isolates ContextVar changes
- Changes made inside ctx.run() are discarded when it returns
- asyncio.current_task() returns the same task even inside copy_context().run()
- So we key by task ID (or thread ID for sync code) to avoid isolation
"""

import threading
import asyncio


# Task-keyed storage: {task_or_thread_id: stack_tuple}
_taint_stacks: dict = {}
_taint_stacks_lock = threading.RLock()


def _get_context_key():
    """Get unique key for current execution context (task ID or thread ID)."""
    try:
        task = asyncio.current_task()
        if task is not None:
            return ("task", id(task))
    except RuntimeError:
        pass  # No running event loop
    return ("thread", threading.current_thread().ident)


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


class TaintStack:
    """
    Stack-based taint tracking for third-party code boundaries.

    Uses task-keyed storage: each async task (or thread for sync code) has its own stack.
    This avoids ContextVar isolation issues from copy_context().run().

    Operations:
    - push(taint): exec_func calls before invoking third-party function
    - pop(): exec_func calls after function returns; returns union of all elements
    - read(): patches call to get source edges; returns union without removing
    - update(taint): patches call to set their output taint; replaces top element
    """

    def _get_stack(self):
        """Get the stack for the current context."""
        key = _get_context_key()
        with _taint_stacks_lock:
            return _taint_stacks.get(key, ())

    def _set_stack(self, stack):
        """Set the stack for the current context."""
        key = _get_context_key()
        with _taint_stacks_lock:
            if stack:
                _taint_stacks[key] = stack
            else:
                _taint_stacks.pop(key, None)  # Clean up empty stacks

    def push(self, taint):
        """Add taint context to top of stack."""
        current = self._get_stack()
        self._set_stack(current + (tuple(taint),))

    def pop(self):
        """Remove top, return union of all elements."""
        current = self._get_stack()
        result = self._union_all(current)
        if current:
            self._set_stack(current[:-1])
        return result

    def read(self):
        """Return union of all elements (don't remove)."""
        return self._union_all(self._get_stack())

    def update(self, taint):
        """Replace top element with new taint."""
        current = self._get_stack()
        if current:
            self._set_stack(current[:-1] + (tuple(taint),))
        else:
            self._set_stack((tuple(taint),))

    def _union_all(self, stack):
        """Return union of all taint tuples in stack."""
        result = set()
        for taint_tuple in stack:
            result.update(taint_tuple)
        return list(result)
