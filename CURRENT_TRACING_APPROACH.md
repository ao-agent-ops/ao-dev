# Current Taint Tracking Implementation

**Status:** The codebase is between refactors and in an inconsistent state. This document describes the current implementation, not the target design (see `TRACING_TAINT.md` for that).

## Overview

The system tracks data flow ("taint") from LLM outputs through program execution using three mechanisms:

1. **AST Transformation** (`ast_transformer.py`) - Rewrites user code at import time
2. **Taint Wrappers** (`taint_wrappers.py`) - Wraps primitives to carry taint info
3. **Runtime Helpers** (`ast_helpers.py`) - Functions called by rewritten code

## Key Data Structures

### TAINT_DICT (WeakKeyDictionary)
- Registered in `builtins` at runtime by `agent_runner.py`
- Maps objects (that support weak refs) to their taint origins: `{obj: [origin_ids]}`
- Used for objects like custom class instances, not for primitives

### ACTIVE_TAINT (ContextVar)
- Thread/async-safe variable for passing taint through third-party code boundaries
- Set before calling third-party functions, read after they return
- Contains list of taint origin IDs

### TaintWrapper
- Wraps primitives (str, int, float, list, dict, tuple) that don't support weak refs
- Stores `_taint_origin` list and `_root_wrapper` reference
- Delegates operations to wrapped object via `bound_access()` partials

## AST Transformations (ast_transformer.py)

The `TaintPropagationTransformer` rewrites user code as follows:

| Original Code | Transformed To |
|---------------|----------------|
| `x` (variable read) | `intercept_access('name', 'x', None)` |
| `obj.attr` | `intercept_access('attr', obj, 'attr')` |
| `obj[key]` | `intercept_access('subscript', obj, key)` |
| `x = value` | `x = intercept_assign('name', 'x', None, value)` |
| `obj.attr = value` | `intercept_assign('attr', obj, 'attr', value)` |
| `obj[key] = value` | `exec_func(operator.setitem, (obj, key, value), {})` |
| `func(args)` | `exec_func(func, (args,), {})` |
| `obj.method(args)` | `exec_func(obj.method, (args,), {})` |
| `a + b` | `exec_func(operator.add, (a, b), {})` |
| `f"hello {x}"` | `taint_fstring_join("hello ", x)` |

## Runtime Functions (ast_helpers.py)

### exec_func(func, args, kwargs)
Main entry point for all function/method calls and operations.

```
1. If func is user code (_is_user_function check): call directly, return result
2. Otherwise (third-party code):
   a. Collect taint from args, kwargs, and bound_self (if method)
   b. Set ACTIVE_TAINT with collected taint
   c. Unwrap all TaintWrapper arguments
   d. Call the function
   e. Wrap result with taint from ACTIVE_TAINT
```

Key detail: For bound methods on TaintWrapper, `exec_func` extracts taint from the wrapper's `_root_wrapper` and updates it with argument taint.

### intercept_access(op_type, obj_or_name, attr_or_none)
Handles reading values with taint propagation.

- `'name'`: Uses frame inspection (`f_locals`, `f_globals`) to look up variable
- `'attr'`: Gets `getattr(obj, attr)`, checks TAINT_DICT for source taint
- `'subscript'`: Gets `obj[key]`, checks TAINT_DICT for source taint

Returns the value wrapped with source's taint if applicable.

### intercept_assign(op_type, obj_or_name, attr_or_none, value)
Handles writing values with taint propagation.

- Extracts taint from the value being assigned
- Updates TAINT_DICT with the taint (if object supports weak refs)
- Performs the actual assignment (unwrapping value first)

### taint(obj, taint_origins)
Applies taint to an object:
- If supports weak refs → add to TAINT_DICT, return unwrapped
- Otherwise → wrap in TaintWrapper, return wrapper

## TaintWrapper Details (taint_wrappers.py)

### Core Design
```python
class TaintWrapper:
    obj: Any           # The wrapped primitive/collection
    _taint_origin: list  # List of taint origin IDs
    _root_wrapper: TaintWrapper  # Reference to root (for nested access)
```

### Key Methods

**`__getattr__(name)`**: Returns a `functools.partial(self.bound_access, name)` instead of the actual attribute. This allows `exec_func` to detect bound methods on TaintWrapper and extract taint from `_root_wrapper`.

**`bound_access(name, *args, **kwargs)`**: Either returns the attribute value (no args) or calls the method (with args). Always returns raw results—taint wrapping is handled by `exec_func`.

**`__getitem__`, `__iter__`**: Wrap returned items with the wrapper's taint.

### taint_wrap(obj, taint_origin, root_wrapper)
Factory function that decides how to apply taint:
```python
1. If already wrapped → return as-is
2. If bool/None/type/function/module/enum → return as-is (not wrappable)
3. If supports weak refs → add to TAINT_DICT, return unwrapped
4. Otherwise → wrap in TaintWrapper
```

### get_taint_origins(val)
Recursively extracts taint from:
- TaintWrapper objects (via `_taint_origin`)
- Partial objects (via `func.__self__._root_wrapper._taint_origin`)
- Nested structures (lists, dicts, tuples, sets)

### untaint_if_needed(val)
Recursively unwraps tainted values:
- TaintWrapper → returns `.obj`
- Collections with tainted items → creates new collection with unwrapped items
- Custom objects with tainted attrs → creates copy with unwrapped attrs

## Known Issues / Inconsistencies

1. **Frame inspection fragility**: `intercept_access` for `'name'` type uses `inspect.currentframe().f_back.f_back` which is brittle and may break with different call depths.

2. **Mixed approaches**: Both `_root_wrapper` (for aggregating taint) and TAINT_DICT (for fine-grained per-object taint) exist, but their interaction is unclear.

3. **Missing exec_line()**: The design doc mentions resetting ACTIVE_TAINT per line via `exec_line()`, but this isn't implemented.

4. **Partial-based attribute access**: When `TaintWrapper.__getattr__` returns a partial, it's unclear how attribute reads (not method calls) are supposed to work—the partial always expects to be called.

5. **TAINT_DICT format**: Current code stores flat lists `{obj: [origins]}` but design doc suggests nested shadow structures `{obj: {"taint_origins": [], "attr": {"taint_origins": []}}}`.

## File Locations

| Concern | File | Key Functions/Classes |
|---------|------|----------------------|
| AST rewriting | `src/server/ast_transformer.py` | `TaintPropagationTransformer` |
| Runtime helpers | `src/server/ast_helpers.py` | `exec_func`, `intercept_access`, `intercept_assign`, `taint` |
| Wrapper class | `src/runner/taint_wrappers.py` | `TaintWrapper`, `taint_wrap`, `get_taint_origins`, `untaint_if_needed` |
| Initialization | `src/runner/agent_runner.py` | Sets up `builtins.TAINT_DICT`, `builtins.ACTIVE_TAINT` |
