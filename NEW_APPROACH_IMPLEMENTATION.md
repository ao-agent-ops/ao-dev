# Implementation Plan: Shadow Mirror Taint Dict

This document outlines the precise code changes needed to implement the approach described in `TRACING_TAINT.md`.

## Key Design Principles

1. **TAINT_DICT is the single source of truth** for all taint information.
2. **TaintWrapper** exists solely to make built-in types weak-referenceable. It stores NO taint.
3. **ACTIVE_TAINT** (ContextVar) passes taint through third-party code boundaries.
4. **Simplicity over completeness** - start with core cases, extend as needed.


## 1. TAINT_DICT Structure

**Format:** `{obj_or_wrapper: {"self": [origin_ids], "attr_name": [origin_ids], ...}}`

- `"self"` key stores the object's own taint origins
- Built-in attribute names (e.g., `"int_var"`, `"str_var"`) store attribute-specific taint
- Non-built-in attributes (objects that support weak refs) get their own TAINT_DICT entries

**Example:**
```python
class MyObj:
    def __init__(self):
        self.int_var = 0      # built-in, stored in parent's shadow
        self.str_var = "hi"   # built-in, stored in parent's shadow
        self.nested = Other() # object, gets own TAINT_DICT entry

my_obj = MyObj()
# TAINT_DICT[my_obj] = {"self": [], "int_var": [], "str_var": []}
# TAINT_DICT[my_obj.nested] = {"self": [], ...}
```

---

## 2. src/server/ast_helpers.py

### 2.1 `add_to_taint_dict_and_return(obj, taint)`

**Purpose:** Wrap built-ins if needed, add to TAINT_DICT with provided taint, return object.

```python
def add_to_taint_dict_and_return(obj, taint):
    """Add obj to TAINT_DICT with given taint, wrapping if needed. Returns obj."""
    import builtins

    result = wrap_if_needed(obj)
    try:
        builtins.TAINT_DICT[result] = {"self": list(taint)}
    except TypeError:
        pass  # Unhashable - can't track
    return result
```

Attributes are populated lazily via `taint_propagating_get` when accessed. This works because the AST rewrites attribute chains from the inside out:

```python
# tainted_obj.a.b becomes:
taint_propagating_get(taint_propagating_get(tainted_obj, "a"), "b")
```

Each intermediate object is in TAINT_DICT before the next level needs its taint.

### 2.2 `get_taint(obj)`

```python
def get_taint(obj):
    """Get taint for an object. Returns [] if not found or unhashable."""
    import builtins

    try:
        if obj in builtins.TAINT_DICT:
            return list(builtins.TAINT_DICT[obj].get("self", []))
    except TypeError:
        pass
    return []
```


### 2.3 `taint_propagating_set(parent_obj, attr_name, val)`

**Purpose:** Set an attribute and update the shadow structure.

```python
def taint_propagating_set(parent_obj, attr_name, val):
    """
    Set parent_obj.attr_name = val with taint propagation.

    Updates TAINT_DICT shadow structure and unwraps val if needed.
    Note: Unhashable parents/values are handled gracefully (assignment still works).
    """
    import builtins
    import weakref

    val_taint = get_taint(val)
    unwrapped_val = untaint_if_needed(val)

    # Try to update TAINT_DICT, but handle unhashable objects gracefully
    try:
        # Ensure parent is in TAINT_DICT
        if parent_obj not in builtins.TAINT_DICT:
            add_to_taint_dict_and_return(parent_obj, taint=[])

        # Check UNWRAPPED val (not wrapper) for weak ref support
        try:
            weakref.ref(unwrapped_val)
            add_to_taint_dict_and_return(unwrapped_val, taint=val_taint)
            if attr_name in builtins.TAINT_DICT[parent_obj]:
                del builtins.TAINT_DICT[parent_obj][attr_name]
        except TypeError:
            # Built-in: store in parent's shadow
            builtins.TAINT_DICT[parent_obj][attr_name] = list(val_taint)
    except TypeError:
        pass  # Unhashable parent - can't track taint, but assignment still works

    # Perform actual assignment with unwrapped value
    setattr(parent_obj, attr_name, unwrapped_val)

    return val
```

### 2.4 `exec_func(func_or_obj, args, kwargs, method_name=None)`

**Purpose:** Execute a function/method with taint tracking at user/third-party boundary.

```python
def exec_func(func_or_obj, args, kwargs, method_name=None):
    """
    Execute func with taint tracking.

    For method calls: pass (obj, args, kwargs, method_name="method")
    For standalone functions: pass (func, args, kwargs)

    User code runs directly with wrapped args.
    Third-party code gets unwrapped args and result is tainted.
    """
    from inspect import iscoroutinefunction
    from aco.runner.taint_wrappers import TaintWrapper

    # === RESOLVE FUNCTION AND COLLECT OBJECT TAINT ===

    if method_name is not None:
        # Method call: func_or_obj is the object
        obj_taint = get_taint(func_or_obj)
        unwrapped_obj = untaint_if_needed(func_or_obj)
        func = getattr(unwrapped_obj, method_name)
    elif isinstance(func_or_obj, TaintWrapper):
        # Wrapped callable being called directly
        obj_taint = get_taint(func_or_obj)
        func = untaint_if_needed(func_or_obj)
    else:
        # Standalone function or bound method
        func = func_or_obj
        obj_taint = get_taint(func.__self__) if hasattr(func, '__self__') else []

    # === USER CODE: pass wrapped args directly ===

    if _is_user_code(func):
        return func(*args, **kwargs)

    # === THIRD-PARTY CODE: collect all taint, unwrap, call ===

    args_taint = []
    for val in args:
        args_taint.extend(get_taint(val))
    for val in kwargs.values():
        args_taint.extend(get_taint(val))

    taint = list(set(obj_taint + args_taint))

    unwrapped_args = tuple(untaint_if_needed(arg) for arg in args)
    unwrapped_kwargs = {k: untaint_if_needed(v) for k, v in kwargs.items()}

    if iscoroutinefunction(func):
        return _exec_async(func, unwrapped_args, unwrapped_kwargs, taint)
    return _exec_sync(func, unwrapped_args, unwrapped_kwargs, taint)


def _exec_sync(func, args, kwargs, taint):
    """Execute sync function with taint tracking."""
    import builtins, asyncio

    builtins.ACTIVE_TAINT.set(taint)
    try:
        result = func(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return _wrap_coroutine_with_taint(result, taint)
        return add_to_taint_dict_and_return(result, taint=taint)
    finally:
        builtins.ACTIVE_TAINT.set([])


async def _exec_async(func, args, kwargs, taint):
    """Execute async function with taint tracking."""
    import builtins

    builtins.ACTIVE_TAINT.set(taint)
    try:
        result = await func(*args, **kwargs)
        return add_to_taint_dict_and_return(result, taint=taint)
    finally:
        builtins.ACTIVE_TAINT.set([])


async def _wrap_coroutine_with_taint(coro, taint):
    """Wrap coroutine to set taint context when awaited."""
    import builtins

    builtins.ACTIVE_TAINT.set(taint)
    try:
        result = await coro
        return add_to_taint_dict_and_return(result, taint=taint)
    finally:
        builtins.ACTIVE_TAINT.set([])


def _is_user_code(func):
    """Check if function is defined in user code."""
    from inspect import getsourcefile
    from aco.common.utils import MODULES_TO_FILES

    if hasattr(func, '__func__'):
        func = func.__func__

    try:
        source_file = getsourcefile(func)
        if source_file:
            return source_file in MODULES_TO_FILES.values()
    except (TypeError, OSError):
        pass
    return False
```

**Async Transparency:** The implementation ensures that:
1. For `async def` functions: `exec_func` returns a coroutine that sets ACTIVE_TAINT when awaited
2. For sync functions returning coroutines: The coroutine is wrapped to preserve taint context
3. User code sees the same behavior as without instrumentation (await works normally)

**Known Limitations:**
- Async generators (`async def` with `yield`) need `inspect.isasyncgenfunction` check
- Regular generators have similar lazy execution issues

### 2.5 `taint_propagating_get(parent_obj, attr_name)`

**Purpose:** Get an attribute with proper taint propagation.

```python
def taint_propagating_get(parent_obj, attr_name):
    """
    Get parent_obj.attr_name with taint propagation.

    Returns:
        The attribute value (wrapped if it's a built-in)
    """
    import builtins

    unwrapped_parent = untaint_if_needed(parent_obj)
    attr_val = getattr(unwrapped_parent, attr_name)

    # Resolve taint: check shadow for built-ins, own entry for objects, fallback to parent
    try:
        shadow = builtins.TAINT_DICT.get(parent_obj, {})
        if attr_name in shadow:
            taint = shadow[attr_name]
        elif attr_val in builtins.TAINT_DICT:
            taint = builtins.TAINT_DICT[attr_val].get("self", [])
        else:
            taint = shadow.get("self", [])
    except TypeError:
        taint = []

    return add_to_taint_dict_and_return(attr_val, taint=list(taint))
```

### 2.6 `ensure_tainted(value)`

**Purpose:** Ensure a value is in TAINT_DICT with its existing taint.

```python
def ensure_tainted(value):
    """
    Ensure value is in TAINT_DICT, return value (wrapped if built-in).
    Used for variable assignments: x = value -> x = ensure_tainted(value)
    """
    return add_to_taint_dict_and_return(value, get_taint(value))
```

### 2.7 Helper: `wrap_if_needed(obj)`

```python
def wrap_if_needed(obj):
    """
    Wrap object in TaintWrapper if it doesn't support weak references.

    Does NOT handle taint - only makes objects weak-referenceable.
    """
    from aco.runner.taint_wrappers import TaintWrapper

    # Don't double-wrap
    if isinstance(obj, TaintWrapper):
        return obj

    # Don't wrap special types
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, type):
        return obj

    import inspect
    if inspect.isfunction(obj) or inspect.ismodule(obj):
        return obj

    # Check weak ref support
    try:
        import weakref
        weakref.ref(obj)
        return obj  # Supports weak refs
    except TypeError:
        return TaintWrapper(obj)  # Needs wrapping
```

---

## 3. src/server/ast_transformer.py

### 3.1 Update Import Injection

```python
# In _inject_taint_imports():
safe_import_code = """
import operator
from aco.server.ast_helpers import (
    exec_func, get_taint, taint_propagating_set, taint_propagating_get,
    ensure_tainted, add_to_taint_dict_and_return, wrap_if_needed,
    taint_fstring_join, taint_format_string, taint_percent_format, taint_open
)
"""
```

### 3.2 Update `visit_Call()`

**Critical:** Check for method calls BEFORE `generic_visit()` to prevent `visit_Attribute` from transforming `obj.method` into `taint_propagating_get(obj, "method")`.

```python
def visit_Call(self, node):
    # Check for method call BEFORE generic_visit
    if isinstance(node.func, ast.Attribute):
        func_name = node.func.attr
        if func_name in dunder_methods:
            return self.generic_visit(node)

        self.needs_taint_imports = True

        # Visit children manually: visit args/kwargs but NOT node.func.attr
        node.args = [self.visit(arg) for arg in node.args]
        node.keywords = [ast.keyword(arg=kw.arg, value=self.visit(kw.value)) for kw in node.keywords]
        node.func.value = self.visit(node.func.value)  # Visit parent obj, not the attribute

        # Transform: obj.method(args) -> exec_func(obj, (args,), {kwargs}, method_name="method")
        args_tuple = ast.Tuple(elts=node.args, ctx=ast.Load())
        kwargs_dict = ast.Dict(
            keys=[ast.Constant(value=kw.arg) if kw.arg else None for kw in node.keywords],
            values=[kw.value for kw in node.keywords]
        )
        new_node = ast.Call(
            func=ast.Name(id="exec_func", ctx=ast.Load()),
            args=[node.func.value, args_tuple, kwargs_dict],  # Pass obj, not obj.method
            keywords=[ast.keyword(arg="method_name", value=ast.Constant(value=func_name))]
        )
        return ast.copy_location(new_node, node)

    # For non-method calls, generic_visit is safe
    node = self.generic_visit(node)

    # Standalone function: func(args) -> exec_func(func, (args,), {kwargs})
    if isinstance(node.func, ast.Name):
        self.needs_taint_imports = True
        args_tuple = ast.Tuple(elts=node.args, ctx=ast.Load())
        kwargs_dict = ast.Dict(
            keys=[ast.Constant(value=kw.arg) if kw.arg else None for kw in node.keywords],
            values=[kw.value for kw in node.keywords]
        )
        new_node = ast.Call(
            func=ast.Name(id="exec_func", ctx=ast.Load()),
            args=[node.func, args_tuple, kwargs_dict],
            keywords=[]
        )
        return ast.copy_location(new_node, node)

    return node
```

**Example transformations:**
```python
# Method call on variable
tainted_str.upper()
# -> exec_func(tainted_str, (), {}, method_name="upper")

# Method call on attribute chain
obj.nested.data.upper()
# -> exec_func(taint_propagating_get(taint_propagating_get(obj, "nested"), "data"), (), {}, method_name="upper")

# Standalone function
len(tainted_list)
# -> exec_func(len, (tainted_list,), {})
```

### 3.4 Update `visit_Attribute()` for Attribute Access

Attribute reads are rewritten to use `taint_propagating_get`, which handles both objects (already in TAINT_DICT) and built-ins (need wrapping).

```python
def visit_Attribute(self, node):
    """Transform attribute access to propagate taint."""
    node = self.generic_visit(node)

    # Only intercept Load context (reading attributes)
    if isinstance(node.ctx, ast.Load):
        self.needs_taint_imports = True

        # obj.attr -> taint_propagating_get(obj, "attr")
        new_node = ast.Call(
            func=ast.Name(id="taint_propagating_get", ctx=ast.Load()),
            args=[
                node.value,  # parent object
                ast.Constant(value=node.attr)  # attribute name as string
            ],
            keywords=[]
        )
        return ast.copy_location(new_node, node)

    return node
```


### 3.5 Update `visit_Assign()` for Attribute Assignments

```python
# obj.attr = value -> taint_propagating_set(obj, "attr", value)
elif isinstance(target, ast.Attribute):
    self.needs_taint_imports = True

    new_node = ast.Expr(value=ast.Call(
        func=ast.Name(id="taint_propagating_set", ctx=ast.Load()),
        args=[
            target.value,
            ast.Constant(value=target.attr),
            node.value
        ],
        keywords=[]
    ))
    return ast.copy_location(new_node, node)
```

### 3.6 Variable Assignments

```python
# x = value -> x = ensure_tainted(value)
elif isinstance(target, ast.Name):
    self.needs_taint_imports = True

    wrapped_value = ast.Call(
        func=ast.Name(id="ensure_tainted", ctx=ast.Load()),
        args=[node.value],
        keywords=[]
    )
    new_node = ast.Assign(targets=[target], value=wrapped_value)
    return ast.copy_location(new_node, node)
```

### 3.7 Other Operations

The following operations also need to be wrapped for taint propagation:

- **Binary operations** (`+`, `-`, `*`, `/`, `//`, `%`, `**`, `<<`, `>>`, `|`, `^`, `&`, `@`)
  - Use `exec_func(operator.add, (a, b), {})`

- **Unary operations** (`-x`, `+x`, `~x`)
  - Use `exec_func(operator.neg, (x,), {})`
  - Note: `not x` is NOT wrapped (preserves control flow)

- **Comparison operations** (`==`, `!=`, `<`, `<=`, `>`, `>=`, `is`, `is not`, `in`, `not in`)
  - Use `exec_func(operator.eq, (a, b), {})`
  - Note: `in` uses `operator.contains` with swapped args

- **Augmented assignments** (`+=`, `-=`, `*=`, etc.)
  - Use `exec_func(operator.iadd, (target, value), {})`

- **Subscript access** (`obj[key]`)
  - Use `exec_func(operator.getitem, (obj, key), {})`

- **Subscript assignment** (`obj[key] = value`)
  - Use `exec_func(operator.setitem, (obj, key, value), {})`

- **Delete statements** (`del obj[key]`)
  - Use `exec_func(operator.delitem, (obj, key), {})`

- **Variable reads** (`x`)
  - No transformation needed - variables already hold wrappers from assignment

- **Attribute reads** (`obj.attr`)
  - Use `taint_propagating_get(obj, "attr")`

See `src/server/ast_transformer.py` methods: `visit_BinOp`, `visit_UnaryOp`, `visit_Compare`, `visit_AugAssign`, `visit_Subscript`, `visit_Delete`.

---

## 4. src/runner/taint_wrappers.py

### 4.1 Minimal TaintWrapper

```python
class TaintWrapper:
    """
    Minimal wrapper for built-in types to make them weak-referenceable.

    Stores NO taint. All taint is in TAINT_DICT.
    Most operations go through AST rewrites, not dunder methods.
    """

    __slots__ = ('obj',)

    def __init__(self, obj):
        object.__setattr__(self, "obj", obj)

    # Delegation
    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "obj"), name)

    def __setattr__(self, name, value):
        if name == "obj":
            object.__setattr__(self, name, value)
        else:
            setattr(object.__getattribute__(self, "obj"), name, value)

    def __getitem__(self, key):
        return object.__getattribute__(self, "obj")[key]

    def __setitem__(self, key, value):
        object.__getattribute__(self, "obj")[key] = value

    def __delitem__(self, key):
        del object.__getattribute__(self, "obj")[key]

    # Control flow (not AST-rewritten)
    def __bool__(self):
        return bool(object.__getattribute__(self, "obj"))

    def __iter__(self):
        obj = object.__getattribute__(self, "obj")
        from aco.server.ast_helpers import add_to_taint_dict_and_return, get_taint
        for item in obj:
            # Preserve each item's own taint
            yield add_to_taint_dict_and_return(item, taint=get_taint(item))

    def __len__(self):
        return len(object.__getattribute__(self, "obj"))

    def __index__(self):
        return object.__getattribute__(self, "obj").__index__()

    def __hash__(self):
        return object.__hash__(self)

    # Context manager
    def __enter__(self):
        return object.__getattribute__(self, "obj").__enter__()

    def __exit__(self, *args):
        return object.__getattribute__(self, "obj").__exit__(*args)

    # Callable
    def __call__(self, *args, **kwargs):
        return object.__getattribute__(self, "obj")(*args, **kwargs)

    # Serialization
    def __reduce__(self):
        return (lambda x: x, (object.__getattribute__(self, "obj"),))

    # Debug
    def __repr__(self):
        return f"TaintWrapper({object.__getattribute__(self, 'obj')!r})"

    # Type transparency
    @property
    def __class__(self):
        return object.__getattribute__(self, "obj").__class__
```

### 4.2 Simplified `untaint_if_needed()`

```python
def untaint_if_needed(val, _seen=None):
    """Recursively unwrap TaintWrapper objects."""
    if _seen is None:
        _seen = set()

    obj_id = id(val)
    if obj_id in _seen:
        return val
    _seen.add(obj_id)

    if isinstance(val, TaintWrapper):
        return untaint_if_needed(object.__getattribute__(val, "obj"), _seen)

    if isinstance(val, dict):
        return {k: untaint_if_needed(v, _seen) for k, v in val.items()}
    if isinstance(val, list):
        return [untaint_if_needed(item, _seen) for item in val]
    if isinstance(val, tuple):
        return tuple(untaint_if_needed(item, _seen) for item in val)
    if isinstance(val, set):
        return {untaint_if_needed(item, _seen) for item in val}

    return val
```

### 4.3 Simplified `get_taint_origins()`

```python
def get_taint_origins(val, _seen=None):
    """Extract taint origins from TAINT_DICT."""
    if _seen is None:
        _seen = set()

    obj_id = id(val)
    if obj_id in _seen:
        return []
    _seen.add(obj_id)

    import builtins

    if hasattr(builtins, 'TAINT_DICT'):
        try:
            if val in builtins.TAINT_DICT:
                return list(builtins.TAINT_DICT[val].get("self", []))
        except TypeError:
            pass

    # Check collections
    origins = set()
    if isinstance(val, (list, tuple, set)):
        for item in val:
            origins.update(get_taint_origins(item, _seen))
    elif isinstance(val, dict):
        for v in val.values():
            origins.update(get_taint_origins(v, _seen))

    return list(origins)
```

---

## 5. src/runner/taint_dict.py (New File)

Thread-safe wrapper around WeakKeyDictionary for concurrent access to TAINT_DICT.

```python
import threading
from weakref import WeakKeyDictionary


class ThreadSafeWeakKeyDict:
    """
    Thread-safe wrapper around WeakKeyDictionary for TAINT_DICT.

    Uses RLock to allow nested access (e.g., when add_to_taint_dict_and_return
    recursively adds child attributes).
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
```

---

## 6. src/runner/agent_runner.py

### 6.1 Initialize TAINT_DICT and ACTIVE_TAINT

```python
# In _setup_environment():
from contextvars import ContextVar
from aco.runner.taint_dict import ThreadSafeWeakKeyDict

builtins.TAINT_DICT = ThreadSafeWeakKeyDict()
builtins.ACTIVE_TAINT = ContextVar("active_taint", default=[])
```

### 6.2 Register Functions

```python
from aco.server.ast_helpers import (
    exec_func, get_taint, taint_propagating_set, taint_propagating_get,
    ensure_tainted, add_to_taint_dict_and_return, wrap_if_needed,
    taint_fstring_join, taint_format_string, taint_percent_format, taint_open
)

builtins.exec_func = exec_func
builtins.get_taint = get_taint
builtins.taint_propagating_set = taint_propagating_set
builtins.taint_propagating_get = taint_propagating_get
builtins.ensure_tainted = ensure_tainted
builtins.add_to_taint_dict_and_return = add_to_taint_dict_and_return
builtins.wrap_if_needed = wrap_if_needed
```

---

## 7. Implementation Order

1. **Phase 1: Infrastructure**
   - Create `src/runner/taint_dict.py` with `ThreadSafeWeakKeyDict`
   - Simplify TaintWrapper (remove `_taint_origin`, `_root_wrapper`)
   - Initialize TAINT_DICT and ACTIVE_TAINT in agent_runner.py
   - Implement `wrap_if_needed()`

2. **Phase 2: Core Functions**
   - Implement `add_to_taint_dict_and_return(obj, taint)` (required taint arg)
   - Implement `get_taint(obj)` (object lookup only)
   - Implement `_is_user_code(func)`
   - Implement `exec_func(func_or_obj, args, kwargs, method_name=None)`

3. **Phase 3: Attribute Handling**
   - Implement `taint_propagating_get()`
   - Implement `taint_propagating_set()`
   - Update AST transformer for assignments and function calls

4. **Phase 4: Cleanup**
   - Remove old code: `intercept_access`, `intercept_assign`, `_taint_origin` handling
   - Rename TAINT_STACK → ACTIVE_TAINT in any remaining code
   - Update tests

---

## 8. Test Strategy

Verify in `tests/taint/`:

1. **Basic propagation**: `x = tainted_func(); y = x` - y has taint
2. **Attribute taint**: `obj.a = tainted; obj.b = other` - independent taint
3. **Third-party boundary**: `result = third_party(tainted)` - result has taint
4. **Unwrapping**: Third-party code receives raw values, not TaintWrapper
5. **Method calls on wrapped built-ins**: `tainted_str.upper()` - result has taint
6. **Chained method calls**: `tainted_str.upper().strip()` - result has taint
7. **Method calls with tainted args**: `tainted_str.replace(other_tainted, "x")` - result has combined taint
