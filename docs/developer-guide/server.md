# Server

The development server is the core of AO. It receives events from user processes, manages the dataflow graph, and controls the UI. All communication goes: agent_runner <-> server <-> UI.

## Overview

The server (`main_server.py`) handles:

- TCP socket communication with runner processes
- Session and run management
- Dataflow graph construction
- LLM call caching
- User edit management
- UI updates

## Server Processes

The server spawns two processes:

### 1. Main Server

Receives all UI and runner messages and forwards them. Core forwarding logic.

### 2. File Watcher

The file watcher has two responsibilities:

- **Pre-compiles all files in user's project:** Reads code, AST-transforms it, stores compiled binary in `~/.cache/ao/pyc`. It polls files to detect user edits and recompile. This is purely a performance optimization so files don't need to be rewritten upon `ao-record`.

- **Git versioning:** On every `ao-record`, it checks if any user files have changed and commits them if so. It adds a version timestamp to the run, so the user knows what version of the code they ran. This git versioner is completely independent of any git operations the user performs. It is saved in `~/.cache/ao/git`. We expect it to commit more frequently than the user, as it commits on any file change once the user runs `ao-record`.

## Server Commands

The server starts automatically when you run `ao-record` or interact with the UI. It also automatically shuts down after periods of inactivity.

```bash
# Manual server management
ao-server start
ao-server stop
ao-server restart
ao-server clear    # Clear all cached data and DB
```

> **Note:** When you make changes to the server code, you need to restart the server for changes to take effect!

## Server Logs

All server logs are written to files (not visible in any terminal). Use these commands to view them:

```bash
ao-server logs          # Main server logs
ao-server rewrite-logs  # File watcher (AST rewrite) logs
ao-server git-logs      # Git versioning logs
```

## Debugging the Server

Check if the server is running:

```bash
ps aux | grep main_server.py
```

Check which processes are using the port:

```bash
lsof -i :5959
```

To see the rewritten Python code (not just the binary):

```bash
export DEBUG_AST_REWRITES=1
```

This will store `.ao_rewritten.py` files next to the original ones that are rewritten.

## Database

We support different database backends (e.g., sqlite, postgres) but currently only expose sqlite to the user. The database stores:

- **Cached LLM calls** - For fast replay during re-runs
- **User edits** - Input/output modifications
- **Graph topology** - For reconstructing past runs

See `src/server/database_backends/sqlite.py` for the sqlite DB schema. Schemas may differ between different DB backends.

### Key Concepts

- **`input_hash`** - LLM calls are cached based on a hash of their inputs, not node IDs (since the graph structure may change)
- **`DatabaseManager`** - Handles all cache operations and user edit storage (see `database_manager.py`)

### Graph Topology Storage

The `graph_topology` column in the `experiments` table stores a dictionary representation of the graph. This allows the server to reconstruct in-memory graph representations for past runs.

## Editing and Caching

### User Experience Goals

1. View past runs with their full graphs, inputs, outputs, labels, and colors
2. Edit inputs/outputs and re-run with cached LLM calls (fast)
3. Persist across VS Code restarts

### How Editing Works

1. User clicks "Edit Input" or "Edit Output" in the UI
2. Edit is stored in the database
3. On re-run, the cached LLM call is retrieved
4. The edit is applied at the appropriate point
5. Downstream LLM calls re-execute with modified data

## Session Management

Each `ao-record` execution creates a session. Within a session:

- Multiple runs can occur (via subruns or restarts)
- Each run builds its own dataflow graph
- The UI displays the current run's graph

### Communication Flow

```
Runner Process <---> Server <---> UI (VS Code/Web)
     │                  │              │
     │  LLM events      │  Graph       │
     │  ───────────>    │  updates     │
     │                  │  ─────────>  │
     │                  │              │
     │  Edit requests   │              │
     │  <───────────    │  <─────────  │
```

## Extending the Server

When modifying server code:

1. Make your changes to files in `src/server/`
2. Restart the server: `ao-server restart`
3. Changes take effect immediately

## Next Steps

- [Taint tracking](taint-tracking.md) - How data flow is tracked
- [API patching](api-patching.md) - How LLM APIs are intercepted
