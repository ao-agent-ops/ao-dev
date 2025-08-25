# Running a user script

![Running develop command](/media/develop_spawn.png)


## develop_shim.py

This is the wrapper around the user's python command. It works like this:

1. User types `aco-launch script.py` (instead of `python script.py`)
2. This drops into an "orchestrator". It registers to the `develop_server` as "shim-control". It's needed for restarting (i.e., managing the lifecycle of the actual process running the user's code). It's communication with `develop_server` is about things like receiving "restart" or "shutdown" commands. Orchestrator spawns a child with `Popen` that will run the monkey-patched user code. 
3. The child process is a python script that has some wrapper code in `launch_scripts.py`, which installs monkey patches, establishes a connection to the server, and then runs the user's actual python program. It registers to the develop_server as "shim-runner". It mainly communicates events in the user's code to the server (e.g., LLM call happened + inputs and outputs). Its stdin, stdout, stderr, etc. will be forwarded to the user's terminal as is. The goal here is to provide the illusion that the user just types `python script.py`.

> Note: Alternatively, if the user doesn't run `develop script.py` from the terminal but from a debugger, things work similarly but there's small changes into how the child process is started and restarted by the orchestrator.

## context_manager.py

Manages context like the session ids for different threads.

Sometimes the user wants to do "subruns" within their `aco-launch` run. For example, if the user runs an eval script, they may want each sample to be a separate run. The can do this as follows:

```
for sample in samples:
    with aco_launch("run name"):
        eval_sample(prompt)
```

This can also be used to run many samples concurrently (see examples in `example_workflows/debug_examples/`).

The implementation of the aco_launch context manager is in `context_manager.py`. The diagram below depicts its message sequence chart:

![Subruns](/media/subrun.png)


## Runtime tracing

## Registering calls

See which functions are executed at runtime.

`sitecustomize.py` applies the monkey patching. It intercepts all calls to LLMs and sends to the `develop_server`: Their input, output, file and line number, and the thread / asynio thread the LLM were called from.


## Data flow between LLM calls

Generally, we use wrappers around primitives, which are defined in `taint_wrappers.py`: For example, strings (`str`) are wrapped in `TaintStr`

The wrappers contain the origin of their "taint" (i.e., which LLM call they stem from) and implement functions such as `__add__`, so when you have `str + TaintStr` or `TaintStr + TaintStr`, taint is propagated through these operators. 

The difficult part are things like f-strings (`f"hello {world}"`) and `format`s (`Hello {}".format(world)`), since those cannot be handled by simply overwriting a string operator. To handle them, we do AST rewrites at runtime:


### AST Rewriting for f-strings and `.format()`
The core logic for rewriting f-strings and .format() calls is in `src/runner/fstring_rewriter.py`:
`FStringTransformer` (subclass of `ast.NodeTransformer`):
`visit_JoinedStr`: This method is called for every f-string node in the AST. It replaces the f-string with a call to `taint_fstring_join`, e.g.:
 - `f"{a} {b}"` becomes `taint_fstring_join(a, b)`. This ensures that any taint on the interpolated values is preserved and propagated.
 - `visit_Call`: This method looks for `.format()` calls on string constants and replaces them with a call to taint_format_string, e.g.: `"Hello {}".format(name)` becomes `taint_format_string("Hello {}", name)`
  
`taint_fstring_join` and `taint_format_string`: These functions (also in `fstring_rewriter.py`) use the taint logic from taint_wrappers.py to combine taint from all arguments and return a TaintStr if any argument is tainted.

### How the AST Rewriter is Installed
 - The function `install_fstring_rewriter()` in `fstring_rewriter.py`:
Installs a custom import hook (`FStringImportFinder`) into sys.meta_path.
    - This import hook ensures that whenever a user module is imported, its source code is parsed, transformed (f-strings and `.format()` calls rewritten), and then executed.
    - The rewriter is installed at runtime by code in:
`src/runner/sitecustomize.py` (which is loaded early via PYTHONPATH tricks).
 - The shim logic in develop_shim.py ensures that the environment is set up so that `sitecustomize.py` is loaded for user scripts.

### Taint Propagation
 - `TaintStr` (in `taint_wrappers.py`): A subclass of str that carries a `_taint_origin` attribute.
 - All string operations (+, format, slicing, etc.) are overridden to propagate taint.
 - `taint_wrap`: Used to wrap values (including OpenAI responses) with taint metadata.

### Putting it Together: Execution Flow
1. User script is run via the develop shim (develop_shim.py).
2. The shim sets up the environment so that:
 - The custom sitecustomize.py is loaded.
 - The f-string rewriter is installed for all user modules.
3. When a user module is imported, the import hook rewrites f-strings and .format() calls to use taint-aware functions.
4. When the user code executes f-strings or .format(), the taint-aware functions are called, and taint is propagated using TaintStr.
5. When LLM calls are made, the taint on the input is checked and, if present, the output is wrapped with a new taint node, allowing you to track data flow between LLM calls.

## Maintainance

We need to patch a lot of API functions. Maintaining them will be challenging but since all of the patches follow a similar pattern, the hope is that AI tools will be pretty good at generating them. Please make your code as clean as possible and try to follow existing conventions. For our own sanity but also so the AI tools work better.

TODO: We need CI/CD tests that detect API changes. Can simply be if API changed (pip upgrade openai, etc) and then send email with change log link.

### Writing a monkey patch

First look at `patch_openai_responses_create` in `monkey_patches/openai_patches.py` to understand how a patch looks like. Also check how patches are applied inside the `__init__` of a client, and how the client-level patch functions are registered in `apply_monkey_patches.py`. Then, writing a patch involves two steps:

1. Write the patch function and apply it in the client-level patch function (client `__init__`). If your patching a new client, you need to create the `__init__` patch function and register it in `apply_monkey_patches.py`.

2. Go to `runner/api_parser.py` and implement the five functions there: setting the input/output string, getting the input/output string, getting model name.
