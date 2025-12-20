# Taint tracking with Shadow Mirror Taint Dict

**Note:** Runtime performance is not a consideration for this system. The focus is on correctness and completeness of taint tracking.

The high-level concept is to maintain a global WeakKeyDictionary `TAINT_DICT`, where each object references point to the taint associated with the object. This involves two challenges:

1. **Determining the taint of attributes:** Consider the following example, which shows how different attributes inside the same object can carry different taint:

```python
parent_obj = func_that_produces_taint()
parent_obj.child_obj_1 = tainted_value_a
parent_obj.child_obj_2 = tainted_value_b

child_var_1 = parent_obj.child_obj_1 # Only carries taint from tainted_value_a
child_var_2 = parent_obj.child_obj_2 # Only carries taint from tainted_value_b
child_var_3 = parent_obj.child_obj_3 # Only carries taint from parent (from function call)
```

Solution: Each attribute gets its own entry in `TAINT_DICT` (i.e., stores taint independently). Attributes are populated lazily when accessed - the AST rewrites attribute chains from the inside out, so each intermediate object is added to TAINT_DICT before the next level needs its taint. Note: In Python, objects can only be modified by *overwriting attributes* or *modifying built-ins* (e.g., `+=` on `int`, `.sort()` on `list`, etc). As a whole, all object manipulations (including different ways to modify built-ins) fall into a small set of cases. We define how taint is propagated for each of these cases.

1. **built-ins (int, str, list, etc.) don't have weak refs:** WeakKeyDictionary `TAINT_DICT` cannot be indexed by built-ins.

Solution: Wrap built-ins in minimal, transparent wrappers such that we can produce a weak ref to the wrapper. The wrappers only exist for built-ins that are "standalone variables" in the user code (opposed to attributes of an object). I.e.:

```python
int_var = 4 # int_var will be wrapped
obj.int_var = 4 # int_var won't be wrapped, it's not a "standalone variable"
```

The wrapper serves solely to reference standalone built-in variables. The actual built-in remains untouched inside the wrapper and its taint is stored inside `TAINT_DICT`.

## Core Architecture

### TAINT_DICT Entries

Every object in the user's code has an entry in `TAINT_DICT` (WeakKeyDictionary). Since WeakKeyDictionary requires objects to support weak references, built-ins (int, str, list, dict, etc.) must be wrapped in TaintWrapper when used as standalone variables. The dict entry of an object looks as follows:

Consider this object:

```python
class MyObj:
    def __init__(self):
        self.int_var = 0
        self.str_var = "hello"
        self.nested_obj = OtherObj()

my_obj = MyObject
```

Then `TAINT_DICT[my_obj]` will look like this:

```python
TAINT_DICT[my_obj] = {"self": [], "int_var": [] "str_var": []}
```

The entry stores the taint origins of itself and its *built-in* attributes inside lists. Note that it does not store the taint for `nested_obj`, as `nested_obj` gets its own entry in `TAINT_DICT`.

### Shadow Structure Creation

The shadow structure of an object `obj` is created and inserted into `TAINT_DICT` via `add_to_taint_dict_and_return(obj, taint)`. This function wraps built-ins if needed, and stores the object with the explicitly provided `taint` inside `TAINT_DICT`. It returns the wrapped object if `obj` was a built-in or the unaltered `obj` if it wasn't.

Attributes are NOT added eagerly. Instead, they are populated lazily when accessed via `taint_propagating_get`. This works because the AST rewrites attribute chains from the inside out (see `add_to_taint_dict_and_return` below).

## Attribute and Subscript Access

### Attribute access

If the attribute is a object (i.e., supports weak references), its taint can simply be looked up in `TAINT_DICT`. If it's a built-in (i.e., doesn't support weak references), it's taint will be stored in its parent. For example: For `obj.some_int`, `some_int`'s text is stored in `TAINT_DICT[obj]['some_int']`. We implement a `get_taint` helper method to handle this distinction and get an attribute's taint. Attribute accesses are wrapped inside `get_taint(...)` in the AST rewrite.

### Method calls

Generally, we wrap method calls inside an exec_func() function during the AST rewrite. I.e.:

```python
out = obj.other_obj.my_method(input_arg) # Becomes: out = exec_func(obj.other_obj, obj.other_obj.my_method, (input_arg,), {})
out = my_function(input_arg) # Becomes: out = exec_func(None, my_function, (input_arg,), {})
```

The signature is `exec_func(parent, func, args, kwargs)` where:
- `parent`: The parent object for method calls (None for standalone functions)
- `func`: The callable itself (bound method, function, etc.)
- `args`: Tuple of positional arguments
- `kwargs`: Dict of keyword arguments

`exec_func()` uses the `_is_user_code(func)` helper function to distinguish between methods defined in user code (whose AST is rewritten) and the ones of third-party libraries.

For user code: Just call the function as is. No unwrapping of inputs or anything else.

For third-party libraries:
1. Get the taint of `parent`. Get the taint of the input args and kwargs.
2. Set the global `ACTIVE_TAINT` list to the combined taints (for monkey-patched code that reads it).
3. Unwrap any inputs if they are wrapped. Note: Object attributes will never contain wrapped attributes.
4. Call the function normally.
5. Call `add_to_taint_dict_and_return(output_obj, taint=collected_taint)` with the explicitly collected taint.
6. Reset `ACTIVE_TAINT` to `[]` in a finally block to prevent stale taint leaking to unrelated code.

**Special cases:** Some operations like UnaryOps (`+=`, etc) and collection mutations (`append()`, `sort()`, etc) don't produce new objects but alter existing ones. In the AST rewrites, we don't wrap them with `exec_func()` but use custom wrappers.

### Subscript access

Subscript accesses do not present a special case. For example:

```python
l = [] # l is wrapped so its wrapper can be added to TAINT_DICT (just like other built-ins)
l.append(tainted_int) # append() is a method call and is wrapped inside a function similar to exec_func (but customized for append)
tainted_int_2 = l[0] # TaintWrapper is transparent to subscripts and returns tainted_int (a TaintWrapper object)
```

### Assignment Operations

Assignments are wrapped inside `taint_propagating_set` functions during the AST transform. E.g.:

```python
obj.other_obj.some_int = tainted_int # Becomes: taint_propagating_set(obj.other_obj, "some_int", tainted_int)
```

`taint_propagating_set` updates the attribute's entry in `TAINT_DICT` and unwraps the incoming object if necessary.

## Pseudo code of core functions

### add_to_taint_dict_and_return(obj, taint)

**Pseudo code:**

1. If obj is a built-in that doesn't have a weak ref: `obj = TaintWrapper(obj)`
2. `TAINT_DICT[obj] = {"self": taint}`
3. `return obj` (this is either the unmodified input object or the wrapped input built-in)

**No recursive attribute scanning:** Attributes are added lazily via `taint_propagating_get` when accessed. This works because the AST rewrites attribute chains (e.g., `obj.a.b`) from the inside out, so each intermediate object is in TAINT_DICT before the next level needs its taint.

**Important:** The `taint` argument is REQUIRED. We never read from ACTIVE_TAINT here to avoid accidentally using stale values.

### get_taint(obj, attr_name=None)

Get taint from an object or attribute:

- `get_taint(x)` → taint of x itself (looks up `TAINT_DICT[x]["self"]`)
- `get_taint(obj, "attr")` → taint of obj.attr

For attribute access: If `obj.attr` is a built-in, get its taint from `TAINT_DICT[obj][attr_name]`. Else, get it from `TAINT_DICT[obj.attr]["self"]`.

### taint_propagating_set(parent_obj, attr_name, val)

Overwrite the shadow entry of `parent_obj.attr_name` with the one of `val`. The shadow entry may be `TAINT_DICT[parent_obj.attr_name]` (`parent_obj.attr_name` is an object) or `TAINT_DICT[parent_obj][attr_name]` (`parent_obj.attr_name` is a built-in). Unwrap `val` if necessary, before actually setting `parent_obj.attr_name` to it.

### exec_func(parent, func, args, kwargs)

**Pseudo code:**

1. If the function is inside the user code (i.e., `_is_user_code(func)` is True), just call `func(*args, **kwargs)` without any additional steps.
2. If `_is_user_code(func)` is False (third-party code):
   a. Get the taint of `parent` (if not None) using `get_taint(parent)`.
   b. Get the taint from all args and kwargs using `get_taint`.
   c. Combine all taints into `collected_taint`.
   d. Set `ACTIVE_TAINT` to `collected_taint` (for monkey-patched code that reads it).
3. Unwrap all inputs if they are wrapped. Note that only inputs to the method might be wrapped, object attributes will never be wrapped.
4. Call the function normally: `result = func(*args, **kwargs)`.
5. Call `add_to_taint_dict_and_return(result, taint=collected_taint)` with the explicitly collected taint.
6. In a `finally` block, reset `ACTIVE_TAINT` to `[]` to prevent stale taint leaking to unrelated code.
7. Return the result.


### Collection methods

As discussed above, we don't use the generic `exec_func` to call methods for collections (e.g., `.append()`) but implement them "manually". Inputs to these methods are not unwrapped, e.g., a list may contain wrapped elements. The goal of the special implementations is to preserve the taint of all collection elements (i.e., the taint of `some_list[0]` or `some_dict["key"]` can still be retrieved). We can list all collection methods using, e.g., `dir(list)` for lists. At a high-level, we can implement these three cases which will cover all methods. We then just need to rewrite the AST to use the appropriate one:

**Three categories of mutations:**
1. **Positional** (append, extend, insert, pop): Mirror operation at same indices
2. **Key-Based** (\_\_setitem\_\_, update, pop): Mirror key assignments/deletions  
3. **Permutation** (sort, reverse): Use "Tag-and-Follow" to reorder shadow elements: Before sorting, zip collection items with their shadow taint entries. After sorting the zipped pairs, extract the reordered shadow list to update TAINT_DICT. E.g.: `sorted_pairs = sorted(zip(collection, shadow_taints), key=lambda x: x[0]); collection[:] = [item for item, _ in sorted_pairs]; shadow_taints[:] = [taint for _, taint in sorted_pairs]`

## Invariants

 - Wrapper objects are never passed to third-party code.
 - Wrapper objects only exist for standalone built-in variables.
 - All AST-rewritten code is robust to wrappers being passed around.
 - `TAINT_DICT` is the single source of truth for tracking taint.

## Concurrency Considerations

- **ACTIVE_TAINT**: Uses ContextVar for async-safe taint propagation. **Important:** ACTIVE_TAINT is ONLY for communicating taint through third-party code boundaries (exec_func → monkey patches). It should NOT be read by regular taint propagation code (add_to_taint_dict_and_return, variable assignments, etc.). Using stale ACTIVE_TAINT values would incorrectly propagate taint.
- **TAINT_DICT**: Requires synchronization for thread-safe shadow tree mutations. We achieve this by using a wrapper around WeakKeyDictionary with a lock.
