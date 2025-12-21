# Taint Tracking

Agent Copilot tracks data flow ("taint") between LLM calls using a combination of taint wrappers, AST rewriting, and a file watcher process.

## Overview

The taint tracking system answers: "Which LLM calls influenced this value?"

When an LLM produces output, that output is "tainted" with the LLM call's ID. As the data flows through the program, the taint information propagates. When tainted data reaches another LLM call, we know there's a data dependency.

## Taint Wrappers

Taint wrappers are Python types that extend built-in types to carry taint information.

### Basic Types

```python
from aco.runner.taint_wrappers import TaintStr, TaintInt, TaintList

# A tainted string knows its origin
tainted = TaintStr("Hello", taint_origin=["llm_call_1"])

# Operations preserve taint
result = tainted + " World"  # Still tainted with llm_call_1

# Combining tainted values combines their origins
other = TaintStr("!", taint_origin=["llm_call_2"])
combined = result + other  # Tainted with both llm_call_1 and llm_call_2
```

### Available Wrapper Types

| Type | Base Type | Use Case |
|------|-----------|----------|
| `TaintStr` | `str` | String values |
| `TaintInt` | `int` | Integer values |
| `TaintFloat` | `float` | Float values |
| `TaintBytes` | `bytes` | Binary data |
| `TaintList` | `list` | List containers |
| `TaintDict` | `dict` | Dictionary containers |
| `TaintObject` | any | Generic wrapper for other objects |

### Utility Functions

```python
from aco.runner.taint_wrappers import (
    get_taint_origins,
    untaint_if_needed,
    is_tainted,
    taint_wrap,
)

# Check if a value is tainted
if is_tainted(value):
    origins = get_taint_origins(value)
    print(f"Value came from: {origins}")

# Get the raw value without taint
raw_value = untaint_if_needed(tainted_value)

# Wrap a value with taint
wrapped = taint_wrap(raw_value, taint_origin=["origin_id"])
```

## AST Rewriting

Taint wrappers handle operations on tainted values, but what about third-party library calls?

```python
import os.path

# This would lose taint information without AST rewriting!
result = os.path.join(tainted_path, "filename.txt")
```

The AST transformer rewrites such calls to preserve taint:

```python
# Original
result = os.path.join(a, b)

# Rewritten to:
result = exec_func(os.path.join, (a, b), {}, user_py_files)
```

### What exec_func Does

1. **Untaint inputs** - Extract raw values and collect taint origins
2. **Execute function** - Call the original function normally
3. **Taint output** - Wrap the result with the combined taint origins

### String Formatting

The transformer also handles string formatting operations:

| Original | Rewritten |
|----------|-----------|
| `f"Hello {name}"` | `taint_fstring_join("Hello ", name)` |
| `"Hello {}".format(name)` | `taint_format_string("Hello {}", name)` |
| `"Hello %s" % name` | `taint_percent_format("Hello %s", name)` |

## File Watcher

The file watcher is a daemon process that pre-compiles AST-rewritten Python files.

### How It Works

1. Server spawns the file watcher on startup
2. File watcher monitors all `.py` files in the user's project
3. When a file changes:
   - Read the source file
   - Apply AST transformations
   - Compile to `.pyc` in `__pycache__`

### Why Pre-compile?

Pre-compilation eliminates runtime overhead:

- AST transformation happens before execution
- Python loads pre-compiled `.pyc` files natively
- No startup delay for the user

### AST Rewrite Verification

To distinguish our `.pyc` files from standard Python-compiled ones:

```python
# Injected as first line of every rewritten module
__ACO_AST_REWRITTEN__ = True
```

The file watcher checks for this marker to determine if recompilation is needed.

## Execution Flow

1. **Server starts** → Spawns file watcher
2. **File watcher** → Pre-compiles all user `.py` files with AST rewrites
3. **User runs `aco-launch`** → Import hook ensures `.pyc` files exist
4. **Python loads** → Uses pre-compiled `.pyc` with taint propagation
5. **Monkey patches** → Intercept LLM calls, taint their outputs
6. **Code executes** → Taint propagates through AST-rewritten operations
7. **LLM call reached** → Untaint inputs, detect origins, report to server

## Why Both AST Rewriting and Monkey Patching?

| Mechanism | Use Case | Reason |
|-----------|----------|--------|
| **Monkey Patching** | LLM API calls | Custom handling for each API (parse inputs/outputs) |
| **AST Rewriting** | All other library calls | Generic taint propagation without per-library code |

## Next Steps

- [API patching](api-patching.md) - How LLM APIs are intercepted
- [Testing](testing.md) - Running the test suite
