# Taint Tracking with ID-Based Dictionary

The high-level concept is to maintain a global `TAINT_DICT` where each object's `id()` maps to its taint origins. By storing a reference to each object alongside its taint, we prevent garbage collection and ensure `id(obj)` remains a stable, unique key.

## Core Architecture

### TAINT_DICT Structure

`TAINT_DICT` is a thread-safe dictionary with the structure:

```python
{id(obj): (obj, [origin_ids])}
```

Where:
- `id(obj)` is the object's memory address (stable while we hold a reference)
- `obj` is the actual object (kept alive to prevent id reuse)
- `[origin_ids]` is the list of taint origin identifiers

Key properties:
1. **Direct storage:** All objects (including built-ins like int, str, list) are stored directly since we use `id()` as the key
2. **Uniform handling:** All objects are treated the same way regardless of type
3. **Prevents id reuse:** Storing the object reference prevents garbage collection, ensuring the id remains unique

### Taint Propagation

Taint flows through the program in two ways:

1. **Explicit taint:** Objects returned from LLM calls carry taint from their origin
2. **Inherited taint:** When accessing an attribute or subscript, if the result has no taint of its own, it inherits the parent's taint

Example:
```python
response = llm_call(prompt)  # response gets taint ["llm:123"]
content = response.content   # content inherits taint ["llm:123"]
first_char = content[0]      # first_char inherits taint ["llm:123"]
```

### ACTIVE_TAINT (ContextVar)

`ACTIVE_TAINT` is a ContextVar used to pass taint through third-party code boundaries. It is ONLY used for communication between `exec_func` and monkey-patched code. Regular taint propagation code should NOT read from ACTIVE_TAINT.

Flow:
1. `exec_func` collects taint from all arguments
2. Sets `ACTIVE_TAINT` to the collected taint
3. Calls the third-party function
4. Third-party code (or monkey patches) can read `ACTIVE_TAINT`
5. `exec_func` adds taint to the result via `add_to_taint_dict_and_return`
6. Resets `ACTIVE_TAINT` to `[]` in a finally block

## Core Functions

### add_to_taint_dict_and_return(obj, taint)

Add an object to TAINT_DICT with explicit taint. Returns the object unchanged.

```python
def add_to_taint_dict_and_return(obj, taint):
    if taint:
        TAINT_DICT.add(obj, taint)  # Stores {id(obj): (obj, taint)}
    return obj
```

**Important:** The `taint` argument is REQUIRED. We never read from ACTIVE_TAINT here to avoid accidentally using stale values.

### get_taint(obj)

Get taint origins for an object. Returns `[]` if not found.

```python
def get_taint(obj):
    return TAINT_DICT.get_taint(obj)  # Returns [] if not in dict
```

### taint_assign(value)

Preserve existing taint when assigning to a variable. Used by AST rewrites for simple assignments like `x = value`.

```python
def taint_assign(value):
    existing_taint = get_taint(value)
    return add_to_taint_dict_and_return(value, taint=existing_taint)
```

### get_attr(obj, attr)

Get an attribute with taint propagation. If the attribute has its own taint, use it. Otherwise, inherit from the parent.

```python
def get_attr(obj, attr):
    result = getattr(obj, attr)
    result_taint = get_taint(result)
    if result_taint:
        return result
    parent_taint = get_taint(obj)
    return add_to_taint_dict_and_return(result, parent_taint)
```

### get_item(obj, key)

Get a subscript with taint propagation. Same inheritance logic as `get_attr`.

```python
def get_item(obj, key):
    result = obj[key]
    item_taint = get_taint(result)
    if item_taint:
        return result
    parent_taint = get_taint(obj)
    return add_to_taint_dict_and_return(result, parent_taint)
```

### exec_func(func_or_obj, args, kwargs, method_name=None)

Execute a function or method with taint tracking.

For **user code** (AST-rewritten code): Call directly. The AST rewrites handle taint propagation.

For **third-party code**:
1. Collect taint from parent object (for methods) and all arguments
2. Set `ACTIVE_TAINT` to the collected taint
3. Call the function
4. Add collected taint to the result
5. Reset `ACTIVE_TAINT` to `[]`

```python
def exec_func(func_or_obj, args, kwargs, method_name=None):
    # Resolve function and collect object taint
    if method_name is not None:
        obj = func_or_obj
        obj_taint = get_taint(obj)
        func = getattr(obj, method_name)
    else:
        obj_taint = []
        func = func_or_obj

    # User code or storing methods: call directly
    if _is_user_function(func) or method_name in STORING_METHODS:
        return func(*args, **kwargs)

    # Third-party: track taint through ACTIVE_TAINT
    all_origins = set(obj_taint)
    all_origins.update(_collect_taint_from_args(args, kwargs))
    taint = list(all_origins)

    ACTIVE_TAINT.set(taint)
    try:
        result = func(*args, **kwargs)
        return add_to_taint_dict_and_return(result, taint=taint)
    finally:
        ACTIVE_TAINT.set([])
```

**Storing methods** (append, extend, insert, add, update, setdefault) are called directly to preserve taint on items being stored in collections.

## AST Transformations

The AST transformer rewrites user code to track taint:

| Original Code | Transformed Code |
|---------------|------------------|
| `x = value` | `x = taint_assign(value)` |
| `obj.attr` | `get_attr(obj, 'attr')` |
| `obj[key]` | `get_item(obj, key)` |
| `obj.attr = value` | `set_attr(obj, 'attr', value)` |
| `obj[key] = value` | `exec_setitem(obj, key, value)` |
| `func(args)` | `exec_func(func, (args,), {})` |
| `obj.method(args)` | `exec_func(obj, (args,), {}, method_name='method')` |
| `a + b` | `exec_func(operator.add, (a, b), {})` |
| `f"hello {x}"` | `taint_fstring_join("hello ", x)` |

## User Code vs Third-Party Code

The system distinguishes between user code and third-party code:

- **User code:** Python files in the user's project. AST-rewritten to handle taint propagation automatically.
- **Third-party code:** Libraries, built-ins, etc. Taint is passed through via `ACTIVE_TAINT`.

The `_is_user_function(func)` helper determines which category a function belongs to by checking its source file against the list of user module files.

## Collection Handling

Collections (list, dict, set) work naturally with this approach:

```python
my_list = []                    # my_list in TAINT_DICT with []
my_list.append(tainted_item)    # append called directly (storing method)
item = my_list[0]               # get_item returns tainted_item with its taint
```

Items stored in collections retain their individual taint. When retrieved, `get_item` first checks if the item has its own taint before falling back to parent taint.

## Invariants

- `TAINT_DICT` is the single source of truth for taint
- `ACTIVE_TAINT` is only for communicating taint through third-party code boundaries
- All taint *propagation* is handled through AST-rewrittes. *Reading and adding* taint is done through monkey patches.

## Concurrency Considerations

- **ACTIVE_TAINT:** Uses ContextVar for async-safe taint propagation across await boundaries
- **TAINT_DICT:** Uses `threading.RLock` for thread-safe access
