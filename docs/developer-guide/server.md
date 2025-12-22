# Server

The development server is the core of AO. It receives events from user processes, manages the dataflow graph, and controls the UI.

## Overview

The server (`develop_server.py`) handles:

- TCP socket communication with runner processes
- Session and run management
- Dataflow graph construction
- LLM call caching
- User edit management
- UI updates

## Starting the Server

```bash
# Manual server management
ao-server start
ao-server stop
ao-server restart
ao-server clear    # Clear all cached data
ao-server logs     # View server logs
```

The server automatically starts when you run `ao-record` if it's not already running.

## Server Logs

Logs are stored at: `~/.cache/ao/logs/server.log`

View logs:

```bash
ao-server logs
```

## Debugging the Server

Check if the server is running:

```bash
ps aux | grep develop_server.py
```

Check which processes are using the port:

```bash
lsof -i :5959
```

## Database

AO uses SQLite to store:

- **Cached LLM calls** - For fast replay during re-runs
- **User edits** - Input/output modifications
- **Graph topology** - For reconstructing past runs

### Key Concepts

- **`input_hash`** - LLM calls are cached based on a hash of their inputs, not node IDs (since the graph structure may change)
- **`CacheManager`** - Handles cache lookups
- **`EditManager`** - Manages user modifications

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
