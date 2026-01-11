# Running a user script

When the user runs `ao-record script.py` (instead of `python script.py`), they create an AgentRunner instance that runs their script.


## agent_runner.py

This is the wrapper around the user's python command. It works like this:

1. Set up environment: 
   1. To track taint (dataflow) through the python program, we rewrite its AST (see server readme). The [file watcher](/src/server/file_watcher.py) performs these rewrites, compiles the resulting AST ("code") and stores the binaries at `~/.cache/ao/pyc`. The [AST rewrite hook](/src/runner/ast_rewrite_hook.py) then makes sure that the code imports the rewritten binaries. Think: python caches binaries in `__pycache__` and loads these pre-compiled binaries if they exist; the AST rewrite hook achieves that the rewritten binaries in `~/.cache/ao/pyc` are loaded and, if a requested binary does not exist, it rewrites the requested code file itself, compiles it, adds it to `~/.cache/ao/pyc`, and loads it for the user. See more below.
   2. There are functions and variables that are used throughout the rewritten user code. They are made importable by adding them to `builtins` module.
2. Connects to the main server. If it isn't running already, it starts it.
3. Starts a thread to listen to `kill` messages from the server (if the user kills/reruns before the user program finished).
4. The "rerun command" is used by the server to issue to the same command the user issued to trigger the current run. It also transmits working dir, env vars, etc. We send it async because it takes long to generate the command and don't want it to be on the critical path.
5. It starts the user program.

## context_manager.py

Manages context like the session ids for different threads.

Sometimes the user wants to do "subruns" within their `ao-record` run. For example, if the user runs an eval script, they may want each sample to be a separate run. They can do this as follows:

```
for sample in samples:
    with ao_launch("run name"):
        eval_sample(prompt)
```

This can also be used to run many samples concurrently (see examples in `example_workflows/debug_examples/`).

## ast_rewrite_hook.py

> [!NOTE]
> We only rewrite "user code". I.e., we blacklist certain modules (e.g., ones defined in `site-packages`) because rewritten code incurs larger import times. This is a pure performance optimization as third-party library imports (`import os`, `import openai`, etc) often import many files. For "third-party functions", we just assume the taint of its inputs is also the taint of its outputs. See [AST transformer](/src/server/ast_transformer.py) and [AST helpers](/src/server/ast_helpers.py) for more details (there are some edge cases).

The import hook is needed because: 
1. **Custom cache location:** The .pyc files are stored in `~/.cache/ao/pyc/` with hashed filenames, not the standard `__pycache__` directory. Python's default import machinery won't find them there.
2. **Fallback compilation:** If the .pyc is missing or stale, the hook compiles on-demand via `rewrite_source_to_code()`.
3. **User code tracking:** It populates `_module_to_user_file` as modules are imported, which the taint system uses to distinguish user code from third-party code.
4. FileWatcher notification: When a file is compiled on-demand (cache miss), it notifies the FileWatcher to start monitoring that file.                                                  
        
The flow is: `ASTImportFinder.find_spec()` → checks if module should be rewritten → `ASTImportLoader.source_to_code()` → tries cached .pyc first → falls back to `rewrite_source_to_code()` if cache miss.

## Computing data flow (graph edges)

To log LLM inputs and outputs and trace data flow ("taint") from LLM to LLM, we use two mechanisms:

1. **Recording LLM calls:** We "[monkey-patch](/src/runner/monkey_patching/)" LLM calls (and MCP tool invocations, ...). When the user imports a package (e.g., `import openai`), patched methods (i) log LLM calls to the server, and (ii) check if input variables have been produced by another LLM and make sure that the output variables are marked (tainted) to be from the current LLM call.

2. **Propagating taint:** For each variable in the user's program, we store if it has been produced by an LLM call (and by which one). We do this inside a globally available `TAINT_DICT` (defined [here](/src/runner/taint_dict.py)) where we map `id(var)` -> `[list of llm origins]`. Inside the rewritten "user code", we rewrite each operation and function call such that taint is propagated. For example, consider the following program:

```python
a = llm_call("hello")
b = llm_call("bye")
c = a + b
c += "hello"
d = llm_call(c)
```

Its functions and operations (e.g., `+`) will be wrapped such that taint is propagated: `a`, `b`, `c` and `d` will all have an entry in `TAINT_DICT`. `a`'s entry will record that `a` was produced by the first LLM call, `b` by the second, `c`'s entry will be a list with both origins, etc.

We don't rewrite "third-party functions" (e.g., `llm_call()`) for performance reasons. Instead, we set `ACTIVE_TAINT` to the union over all taint collected from the inputs. We then normally call the (un-re-written) third-party function. If we installed a patch to the third-party module, it will use `ACTIVE_TAINT` to know the origins of the inputs, and finally set `ACTIVE_TAINT` to be itself. After the third-party function returns, our rewritten code will then set the `TAINT_DICT` entry of the outputs to `ACTIVE_TAINT`. This mirrors: Outputs produced by a third-party function either carry the same taint that was passed to the function, or they carry the taint set by the patch of the third-party function.

There are some more caveats here, which can be best understood by looking at the code in [AST helpers](/src/server/ast_helpers.py). For example:
 - Some functions (e.g, `list.append()`, `dotenv.load_dotenv()`, etc) are treated specially.
 - We *de-intern* strings: Python has a perf opt that makes that `id("hello") == id("hello")` for short strings. This is a problem since the two `"hello"` strings may have been produced by different LLM calls (or one may have been produced by no LLM call at all). We enforce that Python gives a unique id to each string by encoding and decoding it:
```
def _de_intern_string(s):
    """Create a copy of string s with a unique id (not interned)."""
    return s.encode("utf-8").decode("utf-8")
```
 - We keep a reference to each variable in the user code (even if it goes out of scope). The reason is that python will reuse ids if the original objects was garbage collected.

## Intercepting LLM call events (graph nodes)

We write monkey patches at a level as low as possible. I.e., we try to not patch `openai` but `httpx`, the http package that `openai`, `anthropic` and others use so one patch serves many libraries.

## Caching and Reruns

When an LLM call is intercepted (e.g., in [httpx_patch.py](/src/runner/monkey_patching/patches/httpx_patch.py)), the following happens:

1. **Cache lookup**: `DB.get_in_out()` hashes the input and looks it up by `(session_id, input_hash)`. The [database_manager.py](/src/server/database_manager.py) handles all cache operations.

2. **Cache hit**: If a matching entry exists:
   - If `input_overwrite` is set (user edited input in UI), use the modified input instead
   - If `output` is cached (from previous run or user-edited), return it directly without calling the LLM

3. **Cache miss**: If no entry exists or output is `None`:
   - Call the actual LLM with the (possibly overwritten) input
   - Store the result via `DB.cache_output()` for future runs

4. **Graph update**: `send_graph_node_and_edges()` notifies the server to update the UI with the node and its edges (from taint tracking).

**Reruns work deterministically** because:
- The same `session_id` (inherited from parent) means cache lookups find previous entries
- Cached outputs are returned without re-calling the LLM
- Users can modify inputs/outputs via the UI, and these overwrites are respected on rerun
- Randomness is patched (random, numpy, torch) to produce the same sequence given the same seed

This enables interactive debugging: run once, inspect the graph, edit an LLM's input or output, and rerun to see how changes propagate through the dataflow.