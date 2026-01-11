# Server

This is basically the core of the tool. All analysis happens here. It receives messages from the user's agent runner process and controls the UI. I.e., communication goes agent_runner <-> server <-> UI.

 - To check if the server process is still running: `ps aux | grep main_server.py` or check which processes are holding the port: `lsof -i :5959`

## Server processes

1. Main server: Receives all UI and runner messages and forwards them. Core forwarding logic.
2. File watcher:
   - Pre-compiles all files in `user_root`: Reads code, AST-transforms it, stores compiled binary in `~/.cache/ao/pyc`. It polls files to detect user edits and recompile. This is purely a performance optimization so files don't need to be rewritten upon `ao-record`. 
   - The file watcher also includes a git versioner: On every `ao-record`, it checks if any user files have changed and commits them if so. It adds a version time stamp to the run, so the user knows what version of the code they ran. In the future, we will probably also allow the user to jump between versions. This git vesioner is completely independent of any git operations the user performs. It is save in `~/.cache/ao/git`. We expect it to commit ways more frequently than the user, as it commits on any file change once the user runs `ao-record`.

## Server commands and log

Upon running `ao-record` or actions in the UI, the server will be started automatically. It will also automatically shut down after periods of inactivity. Use the following to manually start and stop the server:

 - `ao-server start`
 - `ao-server stop`
 - `ao-server restart`
 
> [!NOTE]
> When you make changes to the server code, you need to restart such that these changes are reflected in the running server!

If you want to clear all recorded runs and cached LLM calls (i.e., clear the DB), do `ao-server clear`.

The server spawns a [file watcher](/src/server/file_watcher.py) process that AST-rewrites user files, compiles the rewritten files and stores them in `~/.cache/ao/pyc`. The file watcher also performs git versioning on the files, so we can display fine-grained file versions to the user (upon them changing files, not only upon them committing using their own git). To see logs of the three, use these commands:

 - Logs of the main server: `ao-server logs`
 - Logs of the file watcher: `ao-server rewrite-logs`
 - Logs of the git versioning: `ao-server git-logs`

Note that all server logs are printed to files and not visible from any terminal.

## Database

We support different database backends (e.g., sqlite, postgres) but (at the time of writing) only expose sqlite to the user. Amongst other things, the database stores cached LLM results and user input overrides (see `llm_calls` table). See [sqlite.py](/src/server/database_backends/sqlite.py) for the sqlite DB schema. Schemas may be different between different DB backends (beyond syntax).

## Taint Tracking via AST Rewrites

We track which variables were produced by LLM calls using an **id-based approach**: a global `TAINT_DICT` maps `id(obj)` → `[list of LLM node origins]`. User code is AST-rewritten so that all operations propagate taint through this dict.

**Key principles:**

1. **Id-based tracking**: Every object's taint is stored by its `id()` in `TAINT_DICT`. No wrapper objects—values flow through the program unchanged.

2. **String de-interning**: Python interns short strings (`id("hello") == id("hello")`), which breaks id-based tracking. We de-intern strings by encoding/decoding them to get unique ids.

3. **User code is rewritten**: The [AST Transformer](/src/server/ast_transformer.py) rewrites operations to propagate taint:
   - `a + b` → `exec_func(operator.add, (a, b), {})`
   - `obj.method(x)` → `exec_func(obj, (x,), {}, method_name="method")`
   - `obj.attr` → `get_attr(obj, "attr")`
   - `x = value` → `x = taint_assign(value)`

4. **Third-party code boundary**: Third-party code (e.g., `os.path.join`) isn't rewritten, so we can't track taint inside it. Instead, `exec_func` uses `ACTIVE_TAINT` as an "escrow":
   - Before call: collect taint from inputs → store in `ACTIVE_TAINT`
   - After call: read `ACTIVE_TAINT` → apply to outputs

   For regular third-party calls, `ACTIVE_TAINT` passes through unchanged (inputs → outputs). But monkey-patched LLM calls can *replace* it with their own node_id, so the output carries the LLM's taint instead of the inputs'.

5. **Monkey patches replace ACTIVE_TAINT**: When an LLM patch (e.g., httpx) intercepts a call, it reads `ACTIVE_TAINT` to discover input origins (→ graph edges), then sets `ACTIVE_TAINT` to its own node_id. When control returns to `exec_func`, this new taint is applied to the result.

**Compilation flow**: The [File Watcher](/src/server/file_watcher.py) polls user files, applies AST rewrites, and stores compiled `.pyc` files in `~/.cache/ao/pyc`. An import hook ensures these pre-compiled files are loaded at runtime.

## Maintainance of EC2 server [OUT OF SERVICE]

### List running process

```
[ec2-user@ip-172-31-42-109 ~]$ docker ps -a
```

Should be 3. (auth (proxy), main_server (backend), frontend (frontend)). E.g.:

```
CONTAINER ID   IMAGE                                                                             COMMAND                  CREATED        STATUS        PORTS                                                           NAMES
a0b7e5115b81   853766430252.dkr.ecr.us-east-1.amazonaws.com/workflow-extension-proxy:latest      "docker-entrypoint.s…"   38 hours ago   Up 38 hours   0.0.0.0:4000->4000/tcp, :::4000->4000/tcp                       workflow-proxy
6913553c4efb   853766430252.dkr.ecr.us-east-1.amazonaws.com/workflow-extension-frontend:latest   "/docker-entrypoint.…"   38 hours ago   Up 38 hours   0.0.0.0:3000->80/tcp, :::3000->80/tcp                           workflow-frontend
0ee59b1ccb71   853766430252.dkr.ecr.us-east-1.amazonaws.com/workflow-extension-backend:latest    "sh -c 'uvicorn src.…"   38 hours ago   Up 38 hours   0.0.0.0:5958-5959->5958-5959/tcp, :::5958-5959->5958-5959/tcp   workflow-backend
```

### Server logs:

```
docker logs XXX
```

`XXX`: `workflow-backend` for main_server, `workflow-proxy` for auth server. `workflow-frontend` is not interesting, should do Right click -> Inspect -> Console

### Debugging

If you want to see the rewritten python code (not only the binary): `export DEBUG_AST_REWRITES=1`.
This will store `.ao_rewritten.py` files next to the original ones that are rewritten. If you don't see these files, maybe you're not rewriting the originals.