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
ao-tool probe <session_id> --nodes <node_id1,node_id2,...>
```

**Options**:
- `--topology`: Return only the graph structure (nodes and edges, no content)
- `--node <node_id>`: Return detailed info for a single node
- `--nodes <node_ids>`: Return detailed info for multiple nodes (comma-separated)
- `--include-content`: When probing nodes, include full input/output content (default: summary only)

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

### 4. `ao-tool edit`

**Purpose**: Modify the input or output of a specific node.

**Usage**:
```bash
ao-tool edit <session_id> <node_id> input '<json_string>'
ao-tool edit <session_id> <node_id> output '<json_string>'
```

**Arguments**:
- `session_id`: Session ID containing the node
- `node_id`: Node ID to edit
- `field`: Either `input` or `output`
- `value`: New value as JSON (the `to_show` structure)

**Output**:
```json
{
  "status": "success",
  "session_id": "uuid",
  "node_id": "node-uuid",
  "field": "input|output"
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
- Calls existing `DB.set_input_overwrite()` or `DB.set_output_overwrite()`
- Validates JSON can be parsed
- Validates the `to_show` structure can be merged with existing `raw` structure
- For output edits, validates result can be converted to API object type
- The edit is stored as an "overwrite" - original is preserved

---

### 5. `ao-tool rerun`

**Purpose**: Re-execute a session, using cached/edited values.

**Usage**:
```bash
ao-tool rerun <session_id>
ao-tool rerun <session_id> --as-new-run
```

**Options**:
- `--as-new-run`: Create a new session instead of updating the existing one
- `--wait`: Block until execution completes
- `--name <name>`: Name for the new run (only with `--as-new-run`)

**Output**:
```json
{
  "status": "started",
  "session_id": "uuid-of-run",
  "is_new_run": false,
  "pid": 12346
}
```

**With `--as-new-run`**:
```json
{
  "status": "started",
  "session_id": "new-uuid",
  "parent_session_id": "original-uuid",
  "is_new_run": true,
  "pid": 12346
}
```

**Implementation notes**:
- Retrieve the original command/cwd/environment from DB
- Set `AO_SESSION_ID` environment variable for rerun (if not `--as-new-run`)
- With `--as-new-run`, create new session but reference parent for cache lookups

---

### 6. `ao-tool edit-and-rerun`

**Purpose**: Combine edit and rerun in a single atomic operation.

**Usage**:
```bash
ao-tool edit-and-rerun <session_id> <node_id> --input '<json>' [--as-new-run]
ao-tool edit-and-rerun <session_id> <node_id> --output '<json>' [--as-new-run]
```

**Options**:
- Same as `edit` and `rerun` combined
- `--wait`: Block until execution completes

**Output**:
```json
{
  "status": "started",
  "session_id": "uuid",
  "node_id": "node-uuid",
  "edited_field": "input",
  "is_new_run": false,
  "pid": 12347
}
```

**Implementation notes**:
- Apply edit first, then trigger rerun
- Atomic from the agent's perspective (one command, one result)

---

### 7. `ao-tool experiments`

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

### 1. `--as-new-run` semantics
When creating a new run from edits, should:
- The new run copy the original's edits as its baseline?
- The new run start fresh but use parent's cache for LLM calls that weren't edited?
- Both (with a flag)?

### 2. Tool description system prompt
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
ao-tool probe <session_id>              # Full session info
ao-tool probe <session_id> --topology   # Just graph structure
ao-tool probe <session_id> --node <id>  # Single node details

### Modify and rerun
ao-tool edit <session_id> <node_id> --output '{"content": "new response"}'
ao-tool rerun <session_id>
ao-tool edit-and-rerun <session_id> <node_id> --output '...' --as-new-run

### Other commands
ao-tool experiments             # List recent sessions
ao-tool terminate <pid>         # Stop a running process

## Workflow Recipes

### Debug a failing agent
1. ao-tool record agent.py
2. ao-tool probe <session_id> --topology  # See the graph
3. ao-tool probe <session_id> --node <failing_node>  # Inspect the failure
4. ao-tool edit <session_id> <node_id> --output '...'  # Fix the output
5. ao-tool rerun <session_id>  # See if downstream succeeds

### A/B test a prompt change
1. Run original: ao-tool record agent.py
2. Edit the input of an LLM node
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
