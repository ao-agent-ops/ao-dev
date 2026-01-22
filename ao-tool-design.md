# AO Tool CLI Design Document

## Overview

`ao-tool` is a CLI interface designed for programmatic interaction with the AO dataflow graph system, primarily intended for use by coding agents like Claude Code. It provides structured, machine-readable output (JSON) for all operations.

## Design Principles

1. **Machine-readable output**: All commands output JSON to stdout for easy parsing
2. **Non-blocking by default**: Long-running operations spawn background processes and return immediately
3. **Idempotent where possible**: Same inputs produce same outputs
4. **Minimal context pollution**: Avoid printing user script output to stdout

---

## Commands

### 1. `ao-tool record`

**Purpose**: Start recording a script execution and return the session ID immediately.

**Usage**:
```bash
ao-tool record <script.py> [script_args...]
ao-tool record -m <module_name> [module_args...]
```

**Options**:
- `-m, --module`: Run script_path as a Python module (like `python -m`)
- `--run-name <name>`: Human-readable name for this run
- `--wait`: Block until execution completes (default: return immediately after spawning)
- `--timeout <seconds>`: When used with `--wait`, maximum time to wait

**Behavior**:
- Spawns `ao-record` as a background process
- Script stdout/stderr goes to a log file, NOT to ao-tool's stdout
- Returns immediately with session_id (unless `--wait` is specified)

**Output (JSON)**:
```json
{
  "status": "started",
  "session_id": "uuid-here",
  "pid": 12345,
  "log_file": "/path/to/log"
}
```

**With `--wait`**:
```json
{
  "status": "completed",
  "session_id": "uuid-here",
  "exit_code": 0,
  "duration_seconds": 45.2
}
```

**Errors**:
```json
{
  "status": "error",
  "error": "Script not found: foo.py"
}
```

**Implementation notes**:
- Use `subprocess.Popen` with stdout/stderr redirected to a temp file
- Store PID in a lightweight tracking mechanism (file or DB) for later termination
- The session_id comes from the server handshake response

---

### 2. `ao-tool probe`

**Purpose**: Query the current state of a session - metadata, graph topology, or specific nodes.

**Usage**:
```bash
ao-tool probe <session_id>
ao-tool probe <session_id> --topology
ao-tool probe <session_id> --node <node_id>
ao-tool probe <session_id> --node <node_id> --preview
ao-tool probe <session_id> --node <node_id> --output
ao-tool probe <session_id> --nodes <node_id1,node_id2,...>
```

**Options**:
- `--topology`: Return only the graph structure (nodes and edges, no content)
- `--node <node_id>`: Return detailed info for a single node (includes full input/output by default)
- `--nodes <node_ids>`: Return detailed info for multiple nodes (comma-separated)
- `--preview`: Truncate all string values to 20 characters for a compact overview
- `--input`: Only show input content (omit output)
- `--output`: Only show output content (omit input)

**Output - Full probe (default)**:
```json
{
  "session_id": "uuid",
  "name": "Run 42",
  "status": "running|finished",
  "timestamp": "2024-01-15T10:30:00Z",
  "result": "success|failure|null",
  "node_count": 5,
  "nodes": [
    {
      "node_id": "node-uuid-1",
      "label": "claude-3-opus",
      "timestamp": "2024-01-15T10:30:05Z",
      "api_type": "anthropic",
      "parent_ids": [],
      "child_ids": ["node-uuid-2"],
      "summary": "User asked about weather...",
      "stack_trace": "file.py:42 in main()\n  file.py:15 in call_llm()"
    }
  ],
  "edges": [
    {"source": "node-uuid-1", "target": "node-uuid-2"}
  ]
}
```

**Output - Topology only (`--topology`)**:
```json
{
  "session_id": "uuid",
  "status": "running",
  "nodes": [
    {"node_id": "node-uuid-1", "label": "claude-3-opus", "parent_ids": [], "child_ids": ["node-uuid-2"]},
    {"node_id": "node-uuid-2", "label": "gpt-4", "parent_ids": ["node-uuid-1"], "child_ids": []}
  ],
  "edges": [
    {"source": "node-uuid-1", "target": "node-uuid-2"}
  ]
}
```

**Output - Single node (`--node`)**:
```json
{
  "node_id": "node-uuid-1",
  "session_id": "uuid",
  "label": "claude-3-opus",
  "api_type": "anthropic",
  "timestamp": "2024-01-15T10:30:05Z",
  "parent_ids": [],
  "child_ids": ["node-uuid-2"],
  "stack_trace": "file.py:42 in main()\n  file.py:15 in call_llm()",
  "input": {
    "model": "claude-3-opus-20240229",
    "messages": [{"role": "user", "content": "What is the weather?"}]
  },
  "output": {
    "content": "I don't have access to real-time weather data...",
    "usage": {"input_tokens": 15, "output_tokens": 42}
  },
  "has_input_overwrite": false,
  "has_output_overwrite": false
}
```

**Implementation notes**:
- Query the database directly (don't need server connection for reads)
- Stack trace should be captured at the point of LLM call and stored with the node
- Summary is the `to_show` field or a truncated version of input/output
- Parent/child IDs enable BFS/DFS traversal by the agent

---

### 3. `ao-tool terminate`

**Purpose**: Stop a running process.

**Usage**:
```bash
ao-tool terminate <pid>
```

**Behavior**:
- Sends SIGTERM for graceful termination
- Waits 5 seconds for process to exit
- Sends SIGKILL if still alive after timeout

**Output**:
```json
{
  "status": "terminated",
  "pid": 12345
}
```

**If process not found**:
```json
{
  "status": "error",
  "error": "Process 12345 not found"
}
```

**Implementation notes**:
- Takes PID directly (returned by `ao-tool record`)
- No `--force` flag - automatic escalation from SIGTERM to SIGKILL after 5s timeout

---

### 4. `ao-tool edit-and-rerun`

**Purpose**: Edit a node's input or output and immediately rerun the session. This is the primary command for interactive debugging - editing without rerunning, or rerunning without editing, are not supported as separate operations.

**Usage**:
```bash
ao-tool edit-and-rerun <session_id> <node_id> --input '<json>'
ao-tool edit-and-rerun <session_id> <node_id> --output '<json>'
ao-tool edit-and-rerun <session_id> <node_id> --output '<json>' --as-new-run
ao-tool edit-and-rerun <session_id> <node_id> --output '<json>' --as-new-run --run-name "My experiment"
```

**Arguments**:
- `session_id`: Session ID containing the node
- `node_id`: Node ID to edit

**Options**:
- `--input <json>`: New input value as JSON (the `to_show` structure) - mutually exclusive with `--output`
- `--output <json>`: New output value as JSON (the `to_show` structure) - mutually exclusive with `--input`
- `--as-new-run`: Create a new session (copy of original) instead of modifying in place
- `--run-name <name>`: Name for the new run (only with `--as-new-run`). Defaults to "Edit of <original name>"
- `--wait`: Block until execution completes
- `--timeout <seconds>`: Timeout when using `--wait`

**Output (started)**:
```json
{
  "status": "started",
  "session_id": "uuid",
  "node_id": "node-uuid",
  "edited_field": "output",
  "pid": 12347,
  "log_file": "/path/to/log"
}
```

**Output (with `--wait`)**:
```json
{
  "status": "completed",
  "session_id": "uuid",
  "node_id": "node-uuid",
  "edited_field": "output",
  "exit_code": 0,
  "duration_seconds": 45.2,
  "log_file": "/path/to/log"
}
```

**Validation errors**:
```json
{
  "status": "error",
  "error": "Invalid JSON: Expecting property name: line 1 column 2"
}
```

**Implementation notes**:
- Validates JSON can be parsed and merged with existing `raw` structure
- For output edits, validates result can be converted to API object type
- The edit is stored as an "overwrite" - original is preserved
- With `--as-new-run`: copies the experiment and all LLM calls to a new session before applying edits
- Retrieves original command/cwd/environment from DB for rerun
- Atomic from the agent's perspective (one command, one result)

---

### 5. `ao-tool experiments`

**Purpose**: List experiments from the database with optional filtering.

**Usage**:
```bash
ao-tool experiments
ao-tool experiments --range :50
ao-tool experiments --range 50:100
ao-tool experiments --regex "eval.*"
```

**Options**:
- `--range <start:end>`: Range of experiments to return (default: `:50`)
  - `:50` - First 50 experiments
  - `50:100` - Experiments 50-99
  - `10:` - All experiments from index 10 onwards
- `--regex <pattern>`: Filter experiments by name using regex

**Output**:
```json
{
  "experiments": [
    {
      "session_id": "uuid",
      "name": "Run 42",
      "timestamp": "2024-01-15T10:30:00Z",
      "result": "success",
      "version_date": "Version Jan 15, 10:30"
    }
  ],
  "total": 150,
  "range": "0:50"
}
```

---


## Open Design Questions

### 1. Tool description system prompt
Should this be:
- A separate command `ao-tool describe` that outputs the full tool documentation
- A static file that Claude Code reads once
- Part of the `--help` output in a machine-readable format

---

## Node Metadata Schema

Every node (API call) contains the following metadata:

| Field | Type | Description |
|-------|------|-------------|
| `node_id` | string | Unique identifier (UUID) |
| `session_id` | string | Parent session identifier |
| `label` | string | Model name or tool name |
| `api_type` | string | API type (e.g., "anthropic", "openai", "httpx") |
| `timestamp` | ISO8601 | When the call was made |
| `stack_trace` | string | Call stack at the point of invocation |
| `parent_ids` | string[] | IDs of nodes whose output fed into this node's input |
| `child_ids` | string[] | IDs of nodes that consume this node's output |
| `input` | object | The API call input (messages, tools, etc.) |
| `output` | object | The API call response |
| `has_input_overwrite` | bool | Whether input has been edited |
| `has_output_overwrite` | bool | Whether output has been edited |

---

## Tool Description System Prompt (Draft)

This section will contain the exact tool definitions for Claude Code to use AO effectively.

```
# AO Tool - Dataflow Debugging for AI Agents

AO Tool lets you record, inspect, and modify the execution of AI agent scripts.
Every LLM call becomes a node in a dataflow graph, showing how data flows between calls.

## Available Commands

### Record a script
ao-tool record <script.py> [args...]
Returns: {"status": "started", "session_id": "...", "pid": ...}

### Inspect a session
ao-tool probe <session_id>                      # Full session info
ao-tool probe <session_id> --topology           # Just graph structure
ao-tool probe <session_id> --node <id>          # Single node with full I/O
ao-tool probe <session_id> --node <id> --preview   # Truncated strings (20 chars)
ao-tool probe <session_id> --node <id> --output    # Only show output
ao-tool probe <session_id> --node <id> --input     # Only show input

### Edit and rerun
ao-tool edit-and-rerun <session_id> <node_id> --output '{"content": "new response"}'
ao-tool edit-and-rerun <session_id> <node_id> --output '...' --as-new-run

### Other commands
ao-tool experiments             # List recent sessions
ao-tool terminate <pid>         # Stop a running process

## Workflow Recipes

### Debug a failing agent
1. ao-tool record agent.py
2. ao-tool probe <session_id> --topology  # See the graph
3. ao-tool probe <session_id> --node <failing_node>  # Inspect the failure
4. ao-tool edit-and-rerun <session_id> <node_id> --output '...'  # Fix and rerun

### A/B test a prompt change
1. Run original: ao-tool record agent.py
2. ao-tool probe <session_id> --node <node_id>  # Inspect the node to edit
3. ao-tool edit-and-rerun <session_id> <node_id> --input '...' --as-new-run
4. Compare the two sessions

### Track only specific code sections
Use the context manager in your Python code:
```python
from ao import ao_launch
with ao_launch("experiment-name"):
    result = my_agent_function()
```
```

---
