# Server

This is basically the core of the tool. All analysis happens here. It receives messages from the user's shim processes and controls the UI. I.e., communication goes shim <-> server <-> UI.


Manually start, stop, restart server:

 - `aco-server start` 
 - `aco-server stop`
 - `aco-server restart`

Some basics: 

 - To check if the server process is still running: `ps aux | grep develop_server.py` or check which processes are holding the port: `lsof -i :5959`

 - When you make changes to `develop_server.py`, remember to restart the server to see them take effect.


## Editing and caching LLM calls

### Goal

Overall, we want the following user experience:

 - We have our dataflow graph in the UI where each node is an LLM call. The user can click "edit input" and "edit output" and the develop epxeriment will rerun using cached LLM calls (so things are quick) but then apply the user edits.
 - If there are past runs, the user can see the graph and it's inputs and ouputs, but not re-run (we can leave the dialogs, and all UI the same, we just need to remember what the graph looked like and what input, output, colors and labels were).

We want to achieve this with the following functionality:

1. For any past run, we can display the graph and all the inputs, outputs, labels and colors like when it was executed. This must also work if VS Code is closed and restarted again.
2. LLM calls are cached so calls with the same prompt to the same model can be replayed.
3. The user can overwrite LLM inputs and ouputs.


### Database

We use a [SQLite](https://sqlite.org) database to cache LLM results and store user overwrites. See `db.py` for their schemas.

The `graph_topology` in the `experiments` table is a dict representation of the graph, that is used inside the develop server. I.e., the develop server can dump and reconstruct in-memory graph representations from that column.

When we run a workflow, new nodes with new `node_ids` are created (the graph may change based on an edited input). So instead of querying the cache based on `node_id`, we query based on `input_hash`.

`CacheManager` is responsible for look ups in the DB.

`EditManager` is responible for updating the DB.

## AST rewrites

To track data flow ("taint") between LLM calls, we use "[taint wrapper](/src/runner/taint_wrappers.py)" that simply wrap an object or builtin (e.g., `str` or `SomeClass`) and record the LLM calls that influenced its value.

We need to propagate this taint through general, third-party libraries (e.g., the output of `os.path.join(a, "LLM produced string")` should be tainted, i.e., we need to remember which LLM influenced the file path).

To achieve this, we rewrite the user's code files and make any third-party library call become like this: `llm_path = os.path.join(a, "LLM produced string")` -> `llm_path = exec_func(os.path.join, a, "LLM produced string")`. [exec_func](/src/server/ast_transformer.py) does the following:
1. Untaint all inputs and remember the (joint) set of all taint origins.
2. Normally execute the rewritten function (e.g., `os.path.join`) with the untainted, "raw" inputs.
3. Wrap the output with a taint wrapper that records the (joint) taint origins from the inputs.

To do these rewrites, the server spawns a [File Watcher](/src/server/file_watcher.py) daemon process that continuously polls `.py` files in the user's code base. If a file changed (i.e., the user edited its code), the [File Watcher](/src/server/file_watcher.py) reads the file and uses the [AST Transformer](/src/server/ast_transformer.py) to rewrite the file. After rewriting a file, the [File Watcher](/src/server/file_watcher.py) compiles it and saves the binary as `.pyc` file in the correct `__pycache__` directory. When the user runs their program (i.e., `aco-launch script.py`), an import hook ensures these rewritten `.pyc` files exist before module imports. This allows `script.py` to directly run with pre-compiled rewrites without runtime overhead.

### AST Rewrite Verification

To distinguish between standard Python-compiled `.pyc` files and our taint-tracking rewritten versions, we inject a verification marker:

As the first line of every rewritten module, we put `__ACO_AST_REWRITTEN__ = True`. The file watcher's `_needs_recompilation()` method uses `is_pyc_rewritten(pyc_path)` to check if existing `.pyc` files contain this marker. If a `.pyc` file exists but lacks the marker (indicating standard Python compilation), it forces recompilation with our AST transformer.

Also see [here](/src/runner/README.md) on how the whole taint propagation process fits together.

### Debugging

If you want to see the rewritten python code (not only the binary): `export ACO_DEBUG_AST_REWRITES=1`. 
This will store `xxx.rewritten.py` files next to the original ones that are rewritten. If you don't see these files, maybe you're not rewriting the originals.