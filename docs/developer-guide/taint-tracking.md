# Taint Tracking

AO tracks data flow ("taint") between LLM calls using an id-based dictionary, AST rewriting, and a file watcher process.

## Overview

The taint tracking system answers: "Which LLM calls influenced this value?"

When an LLM produces output, that output is "tainted" with the LLM call's ID. As the data flows through the program, the taint propagates. When tainted data reaches another LLM call, we know there's a data dependency.

## Core Architecture

### TAINT_DICT

`TAINT_DICT` is a global thread-safe dictionary mapping object IDs to taint origins:

```python
{id(obj): (obj, [origin_ids])}
```

Key properties:
1. **Direct storage:** All objects (including built-ins like int, str, list) are stored directly
2. **Prevents id reuse:** Storing the object reference prevents garbage collection, keeping the id stable
3. **Thread-safe:** Uses `threading.RLock` for concurrent access

### Taint Propagation

Taint flows through the program in two ways:

1. **Explicit taint:** Objects returned from LLM calls carry taint from their origin
2. **Inherited taint:** When accessing an attribute or subscript, if the result has no taint of its own, it inherits the parent's taint

Example:
```python
a = llm_call("hello")  # a gets taint ["llm:123"]
b = llm_call("bye")    # b gets taint ["llm:456"]
c = a + b              # c gets taint ["llm:123", "llm:456"]
d = llm_call(c)        # d gets taint ["llm:789"], edge created from 123,456 -> 789
```

### TAINT_STACK

`TAINT_STACK` passes taint through third-party code boundaries. It's used for communication between `exec_func` (AST-injected) and monkey-patched code.

We don't rewrite "third-party functions" (e.g., `llm_call()`) for performance reasons. Instead:

1. `exec_func` collects taint from all arguments and pushes onto `TAINT_STACK`
2. Calls the (un-rewritten) third-party function
3. If the function is monkey-patched (e.g., LLM call), the patch calls `read()` to get input origins, then `update()` to set its node ID
4. After the function returns, `exec_func` pops the stack and applies taint to outputs

**Why task-keyed storage instead of ContextVar:** LangChain uses `copy_context().run()` which isolates ContextVar changes. We use `asyncio.current_task()` (or thread ID for sync code) as the key instead.

#### Why a Stack? LangChain Example

Consider a LangChain agent with a user-defined tool:

```python
@tool
def get_weather(city: str) -> str:
    data = requests.get(f"https://weather.api/{city}").json()  # third-party call
    return f"Weather in {city}: {data['temp']}"

agent = create_react_agent(llm, [get_weather])
agent.invoke("What's the weather in SF?")
```

The execution flow:
```
1. exec_func(agent.invoke) -> push []
   Stack: [()]

2. LangChain calls LLM #1 (decides to use tool)
   -> httpx patch: read()=[], update([n1])
   Stack: [([n1],)]

3. LangChain calls user's get_weather (AST-rewritten, called directly)
   Inside get_weather, requests.get triggers:
   -> exec_func(requests.get) -> push []
   Stack: [([n1],), ()]
   -> exec_func pops
   Stack: [([n1],)]  <- n1 preserved!

4. LangChain calls LLM #2 (formats final answer)
   -> httpx patch: read()=[n1] (edge n1->n2 created!)
   -> update([n2])
   Stack: [([n2],)]

5. exec_func(agent.invoke) pops
   Stack: []
```

**What the stack solves:** Nested `exec_func` calls (step 3) don't overwrite the outer taint context.

#### Current Limitations

1. **User tool taint not propagated to TAINT_STACK:** If a user's tool returns a tainted variable (from a nested LLM call), that taint is in `TAINT_DICT` but not reflected in `TAINT_STACK`. From the framework's perspective, user tool calls are "taint in = taint out".

2. **User tools not logged as graph nodes:** When LangChain calls a user-defined tool, we don't create a node for it in the dataflow graph.

## Core Functions

The key functions in `taint_ops.py`:

| Function | Purpose |
|----------|---------|
| `add_to_taint_dict_and_return(obj, taint)` | Add object to TAINT_DICT with given taint. De-interns strings. |
| `get_taint(obj)` | Get taint origins for object. Returns `[]` if not found. |
| `taint_assign(value)` | Preserve existing taint on assignment (`x = value`). |
| `get_attr(obj, attr)` | Get attribute with taint inheritance from parent. |
| `get_item(obj, key)` | Get subscript with taint inheritance from parent. |
| `exec_func(func, args, kwargs, method_name)` | Execute function with taint tracking (see below). |

**exec_func behavior:**
- **User code:** Call directly. AST rewrites handle taint propagation.
- **Storing methods** (`append`, `extend`, `insert`, `add`, `update`, `setdefault`): Call directly so stored items retain their taint.
- **Third-party code:** Push/pop TAINT_STACK and apply taint to result.

## Collection Handling

Collections work naturally with id-based tracking:

```python
my_list = []                    # my_list in TAINT_DICT with []
my_list.append(tainted_item)    # append called directly (storing method)
item = my_list[0]               # get_item returns item with its own taint
```

Items stored in collections retain their individual taint. When retrieved, `get_item` first checks if the item has its own taint before falling back to parent taint.

## Invariants

1. `TAINT_DICT` is the single source of truth for taint
2. `TAINT_STACK` is only for communicating taint through third-party code boundaries
3. All taint *propagation* is handled through AST rewrites; *reading and adding* taint is done through monkey patches

## AST Rewriting

The AST transformer rewrites user code to track taint through all operations:

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

## String De-interning

Python interns short strings, making `id("hello") == id("hello")`. This breaks id-based tracking since two `"hello"` strings may have different taint origins.

We de-intern strings by encoding and decoding:

```python
def _de_intern_string(s):
    return s.encode("utf-8").decode("utf-8")
```

## File Watcher

The file watcher is a daemon process that pre-compiles AST-rewritten Python files.

1. Server spawns the file watcher on startup
2. File watcher monitors all `.py` files in the user's project
3. When a file changes: read source, apply AST transformations, compile to `.pyc` in `~/.cache/ao/pyc`

Pre-compilation eliminates runtime overhead since Python loads `.pyc` files natively.

## AST Rewrite Hook

The import hook (`ast_rewrite_hook.py`) is needed because:

1. **Custom cache location:** `.pyc` files are in `~/.cache/ao/pyc/`, not `__pycache__`
2. **Fallback compilation:** If `.pyc` is missing or stale, compile on-demand
3. **User code tracking:** Populates `_module_to_user_file` for distinguishing user vs third-party code
4. **FileWatcher notification:** Notifies FileWatcher when a file is compiled on cache miss

## User Code vs Third-Party Code

We only rewrite "user code" (files not in `site-packages`, etc.) for performance. Third-party library imports often load many files.

For third-party functions, we assume taint of inputs equals taint of outputs (via TAINT_STACK). See `ast_transformer.py` and `taint_ops.py` for edge cases.

## Caching and Reruns

When an LLM call is intercepted (e.g., in `httpx_patch.py`):

1. **Cache lookup**: `DB.get_in_out()` hashes the input and looks up by `(session_id, input_hash)`
2. **Cache hit**: Use cached output (or modified input/output from UI edits)
3. **Cache miss**: Call LLM, store result via `DB.cache_output()`
4. **Graph update**: `send_graph_node_and_edges()` notifies the server

**Reruns work deterministically** because:
- Same `session_id` means cache lookups find previous entries
- Cached outputs returned without re-calling LLM
- UI edits to inputs/outputs are respected on rerun
- Randomness is patched to produce same sequence given same seed

## Why Both AST Rewriting and Monkey Patching?

| Mechanism | Use Case | Reason |
|-----------|----------|--------|
| **Monkey Patching** | LLM API calls | Custom handling for each API (parse inputs/outputs) |
| **AST Rewriting** | All other library calls | Generic taint propagation without per-library code |

## Next Steps

- [API patching](api-patching.md) - How LLM APIs are intercepted
- [Testing](testing.md) - Running the test suite
