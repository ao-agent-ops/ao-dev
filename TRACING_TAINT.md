# Taint tracking with Shadow Mirror Taint Dict

**Note:** Runtime performance is not a consideration for this system. The focus is on correctness and completeness of taint tracking.

The high-level concept is to maintain a global dictionary `TAINT_DICT`, where each object's reference points to the taint it carries. This is very simple in principle but involves some complications as Python built-ins (int, str, list, etc.) do not have references. In the following, we therefore describe an approach that mitigates this issue.

## Core Architecture

### TAINT_DICT and Shadow Trees

Every object in the user's code has an entry in TAINT_DICT (WeakKeyDictionary). Since WeakKeyDictionary requires objects to support weak references, built-ins (int, str, list, dict, etc.) must be wrapped in TaintWrapper when used as standalone variables. This wrapper serves solely to enable TAINT_DICT tracking for standalone variables. The actual built-in remains untouched inside the wrapper:

```python
# Objects instantiated in user code are added directly to TAINT_DICT
o = MyObject()  # TAINT_DICT[o] = {shadow structure}

# Built-ins: Wrapped when standalone, unwrapped when nested inside an object
status = 0       # status = TaintWrapper(0), TAINT_DICT[status] = {"taint_origins": []}
obj.status = 0   # Stored unwrapped, shadow in TAINT_DICT[obj]["status"] = {"taint_origins": []}
```

### Shadow Structure Creation

The shadow structure of an object `obj` is created and inserted into `TAINT_DICT` via `add_to_taint_dict_and_return(obj)`. An object's shadow structure **only mirrors built-in attributes** (int, str, list, dict). Objects that support weak references get their own separate `TAINT_DICT` entries instead of being mirrored:

```python
# Example object structure:
r = Response()  # has r.nested_obj (object) and r.status (int)
# TAINT_DICT entry created:
# TAINT_DICT[r] = {
#     "taint_origins": [],
#     "status": {"taint_origins": []}  # Built-in: mirrored in shadow
#     # nested_obj NOT mirrored - has its own entry
# }
```

`r.nested_obj` will get its own `TAINT_DICT` entry when `TAINT_DICT[r.nested_obj]` is accessed for the first time (i.e., `add_to_taint_dict_and_return` is called lazily).

## Attribute and Subscript Access

### Attribute access chains

The AST transformer rewrites access chains to propagate taint through `TAINT_STACK`:

```python
# Original: tainted_response.contents[0].text
# Transforms to:
add_to_taint_dict_and_return(
    taint_propagating_get('attr',
        taint_propagating_get('subscript', 
            taint_propagating_get('attr', tainted_response, 'contents'),
            0),
        'text')
)
```

`taint_propagating_get` updates the global `TAINT_STACK` variable by checking the taint of the input object in `TAINT_DICT`. This recursive "traversal" allows attributes to inherit taint from their parents while also considering that different taint may have been set at deeper levels. Specifically, it allows for the following, fine-grained distinguishment: 

```python
parent_obj = func_that_produces_taint()  # parent_obj is tainted from function call
parent_obj.child_obj_1 = tainted_value_a # Only child_obj_1 will carry tainted_value_a taint
parent_obj.child_obj_2 = tainted_value_b # Only child_obj_2 will carry tainted_value_b taint

child_var_1 = parent_obj.child_obj_1 # Only carries taint from tainted_value_a
child_var_2 = parent_obj.child_obj_2 # Only carries taint from tainted_value_b
child_var_3 = parent_obj.child_obj_3 # Only carries taint from parent (from function call)
```

Also refer to the pseudo code of `taint_propagating_get`.

### Method calls

We wrap method calls inside an exec_func() function during the AST rewrite. For more details, refer to the pseudo code of exec_func() below. 

At a high-level method calls is as follows:
 - We distinguish between functions and methods that are defined in user code versus in third-party lirbaries. We define user code as all code inside a project_root.
 - Inside the project root, code is AST-rewritten. For any AST rewritten code, passing TaintWrapper objects into functions is harmless. So, when we call a method that's defined inside user code (i.e., has been rewritten), we just pass TaintWrapper objects as they are.
 - However, there is a boundary to third-party libraries where passing TaintWrappers is not safe. We therefore unwrap any TaintWrappers before passing them into a third-party library and record the variable's taint inside `TAINT_STACK`. After the third-party method returns, we call `add_to_taint_dict_and_return` on its output (i.e., wrap if the output is a built-in and store the output in `TAINT_DICT` with `TAINT_STACK` taint).
 - The reason that we assoiate `TAINT_STACK` taint with the output is because some third-party libraries are instrumentalized to overwrite `TAINT_STACK`. If not, the taint propagation follows a `taint in = taint out` pattern.

**Special case:** Although TaintWrappers are generally defined outside project root (i.e., they are "third-party code"), we don't unwrap inputs that are passed to them (e.g., for `TaintWrapper.append(tainted_int)`, tainted_int is not unwrapped). We effectively treat them as user code.

The way taint is propagated is by appending to or overwriting an object's entry in the `TAINT_DIR`. For example:

```python
TaintWrapper(5) += TaintWrapper(2) # The taint of the second (2) TaintWrapper is appended to `TAINT_DICT`[first TaintWrapper (5)
user_code_obj.third_party_obj.nested_obj.some_method(tainted_input) # append taint of tainted_input to TAINT_DICT[user_code_obj.third_party_obj]
user_obj.nested_obj = TaintWrapper(5) # Nothing needs to be done, pointer update takes care of it
```

**Special case:** Although TaintWrappers are generally defined outside project root (i.e., they are "third-party code"), we don't unwrap inputs that are passed to them (e.g., for `TaintWrapper.append(tainted_int)`, tainted_int is not unwrapped). We effectively treat them as user code.

### Subscript access

Subscript access follows the patterns described above. Collections (e.g., list, set, dict, tuple) are built-ins, i.e., they don't have a weak reference. We therefore wrap them when we add them to `TAINT_DICT`. TaintWrapper makes sure that the wrapper around collections works transparently (i.e., slicing, subscripts, etc. all work).

So for example:

```
i = 5 # i is wrapped: i = add_to_taint_dict_and_return(5)
l = [] # l is wrapped: l = add_to_taint_dict_and_return([])
l.append(i) # i is passed into append without unwrapping, since l is a TaintWrapper (considered user code)
# Result: When l[0] is accessed, we return i's TaintWrapper with the correct taint
```

However, to correctly map the taint in `TAINT_DICT` to the representation in the collection, **we treat collection methods like append, sort, reverse as special cases:** The AST transformer detects collection methods (append, sort, etc.) and injects shadow synchronization code. This works for both wrapped standalone collections and unwrapped nested collections.

### Assignment Operations
Assignments are rewritten by the AST into `wrapper_aware_assign` functions. If we're assigning to an object defined in user code, we just go ahead. Otherwise, we unwrap if needed, and then do the assignment.

## Concurrency Considerations

- **TAINT_STACK**: Uses ContextVar for async-safe taint propagation
- **TAINT_DICT**: Requires synchronization for thread-safe shadow tree mutations. We achieve this by using a wrapper around WeakKeyDictionary with a lock.
s
## Pseudo code of core functions

### add_to_taint_dict_and_return(obj)

**Pseudo code:**

1. If obj is a built-in that doesn't have a weak ref: `obj = TaintWrapper(obj)`
2. `TAINT_DICT[ref(obj)] = TAINT_STACK`
3. `return obj` (this is either the unmodified input object or the wrapped input built-in)

### taint_propagating_get(access_type, obj, key)

**Inputs:**

 - access_type can be "attr" or "subscript"
 - `obj` is the object the access is performed on
 - `key` is the attribute or dict key name, or the slice (e.g., `"my_attr"` or `"my_dict_key`" or `slice(1,3)`)

**Pseudo code:**

We don't track taint through "third-party code" (i.e., code outside of project_root). If `obj` is defined outside the `project_root`, just return the plain object, i.e.: if access_type == attr: `return obj.key`, else `obj[key]`

If `obj` is defined inside project_root, we propagate taint. Do the following:

1. If `obj` is an object with a weak ref:
   - If `ref(obj)` is in `TAINT_DICT`: `TAINT_STACK = TAINT_DICT[ref(obj) or TAINT_STACK`. 
   - If it's not in `TAINT_DICT`: `_ = add_to_taint_dict_and_return(obj)`
2. If access_type == "attr": `accessed_obj = obj.key`; Else: `accessed_obj = obj[key]`
3. If `accessed_obj` is a built-in with no weak ref: 
   - `TAINT_STACK = TAINT_DICT[ref(obj)][key][taint_origins] or TAINT_STACK`
   - `accessed_obj = add_to_taint_dict_and_return(accessed_obj)`
4. Return `accessed_obj`

### exec_func(obj, method_name, *args, **kwargs)

**Example:**

`out = tainted_obj.nested_obj.other_obj.my_method(tainted_input)`

**AST rewrite of example:**

```
out = exec_func(
        taint_propagating_get('attr',
                taint_propagating_get('attr', tainted_obj, 'nested_obj'),
            'other_obj'),
      "my_method",
      tainted_input)
```

**Pseudo code for example:**

1. We run `taint_propagating_get` for `tainted_obj.nested_obj.other_obj` (i.e., AST transformer does the nested rewrites with `taint_propagating_get`). After that, we have `TAINT_STACK` correctly set.
2. We get the taint of `tainted_input`: `input_taint = TAINT_DICT[ref(tainted_input)]`
3. We append the input_taint to TAINT_STACK: `TAINT_STACK += input_taint`
4. If `tainted_input` is wrapped, we unwrap it: `tainted_input = unwrap_if_needed(tainted_input)`
5. We get the method (`method = getattr(obj, method_name)`) and normally execute it:  `out = tainted_obj.nested_obj.other_obj.method(tainted_input)`
6. We add the output to `TAINT_DICT` (wrap it if needed) and return: `return add_to_taint_dict_and_return(out)` 


### Collection methods

As discussed above, we implement methods for collections (e.g., `.append()`) "manually". We can list all such methods using, e.g., `dir(list)` for lists. Our high-level approach is below:

**Three categories of mutations:**
1. **Positional** (append, extend, insert, pop): Mirror operation at same indices
2. **Key-Based** (\_\_setitem\_\_, update, pop): Mirror key assignments/deletions  
3. **Permutation** (sort, reverse): Use "Tag-and-Follow" to reorder shadow elements: Zip your actual data with this index map. E.g.L zipped = list(zip(actual_data, obj_references in shadow list in TAINT_DICT)).

```python
# AST transformation concept:
collection.append(item)            # Original operation
add_to_taint_dict_and_return(item) # Shadow operation (injected by AST)
```

### Resetting TAINT_STACK

`TAINT_STACK` needs to be reset before every line. In the AST rewrite, every line is wrapped with `exec_line()`. `exec_line` just does `TAINT_STACK = []`.