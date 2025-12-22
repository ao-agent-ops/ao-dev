# Taint Tracking

AO tracks data flow ("taint") between LLM calls using an ID-based dictionary, AST rewriting, and a file watcher process.

## Overview

The taint tracking system answers: "Which LLM calls influenced this value?"

When an LLM produces output, that output is "tainted" with the LLM call's ID. As the data flows through the program, the taint information propagates. When tainted data reaches another LLM call, we know there's a data dependency.

## Core Architecture

### TAINT_DICT

`TAINT_DICT` is a global thread-safe dictionary that maps object IDs to their taint origins:

```python
{id(obj): (obj, [origin_ids])}
```

Where:
- `id(obj)` is the object's memory address (stable while we hold a reference)
- `obj` is the actual object (kept alive to prevent id reuse)
- `[origin_ids]` is the list of taint origin identifiers

Key properties:
1. **Direct storage:** All objects (including built-ins like int, str, list) are stored directly
2. **Uniform handling:** All objects are treated the same way regardless of type
3. **Prevents id reuse:** Storing the object reference prevents garbage collection

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

`ACTIVE_TAINT` is a ContextVar used to pass taint through third-party code boundaries. It is ONLY used for communication between `exec_func` and monkey-patched code.

Flow:
1. `exec_func` collects taint from all arguments
2. Sets `ACTIVE_TAINT` to the collected taint
3. Calls the third-party function
4. Third-party code (or monkey patches) can read `ACTIVE_TAINT`
5. `exec_func` adds taint to the result
6. Resets `ACTIVE_TAINT` to `[]`

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

### What exec_func Does

For **user code** (AST-rewritten): Calls directly. The AST rewrites handle taint propagation.

For **third-party code**:
1. Collect taint from parent object (for methods) and all arguments
2. Set `ACTIVE_TAINT` to the collected taint
3. Call the function
4. Add collected taint to the result
5. Reset `ACTIVE_TAINT` to `[]`

## File Watcher

The file watcher is a daemon process that pre-compiles AST-rewritten Python files.

### How It Works

1. Server spawns the file watcher on startup
2. File watcher monitors all `.py` files in the user's project
3. When a file changes:
   - Read the source file
   - Apply AST transformations
   - Compile to `.pyc` in `__ao_cache__`

### Why Pre-compile?

Pre-compilation eliminates runtime overhead:

- AST transformation happens before execution
- Python loads pre-compiled `.pyc` files natively
- No startup delay for the user

## Execution Flow

1. **Server starts** → Spawns file watcher
2. **File watcher** → Pre-compiles all user `.py` files with AST rewrites
3. **User runs `ao-record`** → Import hook ensures `.pyc` files exist
4. **Python loads** → Uses pre-compiled `.pyc` with taint propagation
5. **Monkey patches** → Intercept LLM calls, add taint to outputs via TAINT_DICT
6. **Code executes** → Taint propagates through AST-rewritten operations
7. **LLM call reached** → Extract taint origins, report to server

## User Code vs Third-Party Code

The system distinguishes between:

- **User code:** Python files in the user's project. AST-rewritten to handle taint propagation automatically.
- **Third-party code:** Libraries, built-ins, etc. Taint is passed through via `ACTIVE_TAINT`.

## Why Both AST Rewriting and Monkey Patching?

| Mechanism | Use Case | Reason |
|-----------|----------|--------|
| **Monkey Patching** | LLM API calls | Custom handling for each API (parse inputs/outputs) |
| **AST Rewriting** | All other library calls | Generic taint propagation without per-library code |

## Next Steps

- [API patching](api-patching.md) - How LLM APIs are intercepted
- [Testing](testing.md) - Running the test suite

## Reference

For detailed implementation, see `src/server/taint_propagation.md`.
