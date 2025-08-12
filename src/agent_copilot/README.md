# Core functionalities

![Running develop command](/media/develop_spawn.png)


## Server

This is basically the core of the tool. All analysis happens here. It receives messages from the user's shim processes and controls the UI. I.e., communication goes shim <-> server <-> UI.


Manually start, stop, restart server:

 - `aco-server start` 
 - `aco-server stop`
 - `aco-server restart`

Some basics: 

 - To check if the server process is still running: `ps aux | grep develop_server.py` or check which processes are holding the port: `lsof -i :5959`

 - When you make changes to `develop_server.py`, remember to restart the server to see them take effect.


## develop_shim.py

This is the wrapper around the user's python command. It works like this:

1. User types `aco-launch script.py` (instead of `python script.py`)
2. This drops into an "orchestrator". It registers to the `develop_server` as "shim-control". It's needed for restarting (i.e., managing the lifecycle of the actual process running the user's code). It's communication with `develop_server` is about things like receiving "restart" or "shutdown" commands. Orchestrator spawns a child with `Popen` that will run the monkey-patched user code. 
3. Child installs monkey patches. It registers to the develop_server as "shim-runner". It runs the actual python code from the user. It communicates with the server about inputs and outputs to LLM calls (etc). Its stdin, stdout, stderr, etc. will be forwarded to the user's terminal as is.

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

## Editing and caching

### Goal

Overall, we want the following user experience:

 - We have our dataflow graph in the UI where each node is an LLM call. The user can click "edit input" and "edit output" and the develop epxeriment will rerun using cached LLM calls (so things are quick) but then apply the user edits.
 - If there are past runs, the user can see the graph and it's inputs and ouputs, but not re-run (we can leave the dialogs, and all UI the same, we just need to remember what the graph looked like and what input, output, colors and labels were).

We want to achieve this with the following functionality:

1. For any past run, we can display the graph and all the inputs, outputs, labels and colors like when it was executed. This must also work if VS Code is closed and restarted again.
2. LLM calls are cached so calls with the same prompt to the same model can be replayed.
3. The user can overwrite LLM inputs and ouputs.


### Database

We use a [SQLite](https://sqlite.org) database to cache LLM results and store user overwrites. We have the following 2 tables:

```sql
CREATE TABLE experiments (
    session_id TEXT PRIMARY KEY,
    graph_topology TEXT,
    timestamp TEXT DEFAULT (datetime('now')),
    cwd TEXT,
    command TEXT,
    code_hash TEXT
)
```

and

```sql
CREATE TABLE llm_calls (
    session_id TEXT,
    node_id TEXT,
    model TEXT,
    input TEXT,
    input_hash TEXT,
    input_overwrite TEXT,
    input_overwrite_hash TEXT,
    output TEXT,
    color TEXT,
    label TEXT,
    api_type TEXT,
    timestamp TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (session_id, node_id)
)
```

The `graph_topology` in the `experiments` table is a dict representation of the graph, that is used inside the develop server. I.e., the develop server can dump and reconstruct in-memory graph representations from that column.

When we run a workflow, new nodes with new `node_ids` are created (the graph may change based on an edited input). So instead of querying the cache based on `node_id`, we query based on `input_hash`.

`CacheManager` is responsible for look ups in the DB.

`EditManager` is responible for updating the DB.
