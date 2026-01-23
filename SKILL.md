---
name: ao
description: ao helps you develop and maintain adaptable agentic systems. It extends Claude Code with context-optimized observability, accelerated A/B testing, a curated playbook of agent development techniques, and dynamic runtime lesson injection. Use when actively developing or improving agentic systems.
---

# ao

## Overview

- **Integrated Observability** – Record agent traces as dataflow graphs with zero code changes
- **Accelerated A/B Testing** – Edit node inputs/outputs and rerun to see how changes propagate
- **Lessons** – Inject learned lessons into agent context dynamically at runtime
- **Design Guide** – Query curated agent development techniques with problems you are encountering

---

## Integrated Observability

Record agent execution as a graph where nodes are LLM/tool calls and edges are data dependencies.

### Record a script
The keyword `record` can be thought of as a replacement for the `python` command.
Wrong:
```
uv run ao-tool record python -m some.module --arg1
```

Correct:
```
uv run ao-tool record -m some.module --arg1
```

```bash
ao-tool record agent.py                       # Start recording, return immediately
ao-tool record --wait agent.py                # Block until script completes
ao-tool record --wait --timeout 60 agent.py   # Wait with 60s timeout
ao-tool record -m my_module                   # Run as Python module
ao-tool record --run-name "Eval run" agent.py # Name the run
```

### Inspect a session
```bash
ao-tool probe <session_id>                    # Full session with all nodes
ao-tool probe <session_id> --topology         # Graph structure only
ao-tool probe <session_id> --node <node_id>   # Single node with full I/O
ao-tool probe <session_id> --node <node_id> --preview   # Truncated strings (20 chars)
ao-tool probe <session_id> --node <node_id> --output    # Only show output
ao-tool probe <session_id> --node <node_id> --input     # Only show input
ao-tool probe <session_id> --nodes <id1,id2>            # Multiple nodes
```

### List and manage experiments
```bash
ao-tool experiments                   # List recent sessions
ao-tool experiments --range :20       # First 20 experiments
ao-tool experiments --regex "eval.*"  # Filter by name
ao-tool terminate <pid>               # Stop a running process
```

---

## Accelerated A/B Testing

Edit a node's input or output and rerun the session to see how changes propagate.
```bash
ao-tool edit-and-rerun <session_id> <node_id> --output '<json>'
ao-tool edit-and-rerun <session_id> <node_id> --input '<json>'
ao-tool edit-and-rerun <session_id> <node_id> --output '<json>' --as-new-run
ao-tool edit-and-rerun <session_id> <node_id> --output '<json>' --as-new-run --run-name "My test"
ao-tool edit-and-rerun <session_id> <node_id> --output '<json>' --wait --timeout 30
```

| Option | Description |
|--------|-------------|
| `--input` / `--output` | New value as JSON (mutually exclusive) |
| `--as-new-run` | Create a copy instead of modifying in place |
| `--run-name` | Name for the new run (requires `--as-new-run`) |
| `--wait` | Block until execution completes |
| `--timeout` | Timeout in seconds (with `--wait`) |

---

## Lessons

TODO: Document lesson injection API, lesson authoring, and storage.

---

## Design Playbook

Query curated agent development techniques when encountering design problems.

### Start the playbook server
```bash
ao-tool playbook start-server  # Required once per session
```

### Query the design guide
```bash
ao-tool playbook design-guide-query --query 'The model does not follow output schemas.'
ao-tool playbook design-guide-query --query 'How to handle JSON extraction from LLM outputs?' --top-k 5
```

| Option | Description |
|--------|-------------|
| `--query`, `-q` | The problem or question to search for (required) |
| `--top-k`, `-k` | Number of results to return (default: 3) |

---

## Workflow Recipes

### Setup – ALWAYS propose these when starting to use this tool

1. **Start the playbook server** (for design guide queries):
   ```bash
   ao-tool playbook start-server
   ```

2. **Integrate the lessons API**:
   ```python
   # Example code here
   ```

3. **Check for caching conflicts**: Scan the user-code for caching mechanisms (such as ad-hoc implementation of LLM-input caching or benchmark caching) that can interfere with the re-run capability. If you encounter such caching, flag this to the user and propose to change it by, for example, being able to disable caching with a `--no-cache` flag. **NOTE:** Caching that happens at the API provider level, for example using `cache_control` in the Anthropic API is OK!

### Debugging a failing agent

1. **Set up evaluation criteria**
   - *Correctness*: Add verification code (test cases, state checks, exception handling)
   - *Cost/latency*: Query with `ao-tool experiments --regex ...` to get the cost and time of a run

2. **Capture execution**: `ao-tool record agent.py`

3. **Locate the error** using `ao-tool probe`:
   - Start with topology: `ao-tool probe <session_id> --topology`
   - Small graphs (<10 nodes): dump everything with `ao-tool probe <session_id>`
   - Large graphs: traverse nodes via `ao-tool probe <session_id> --node <node_id>`

### Implementing a fix

- **Simple, generic errors**: Modify the system prompt directly
- **Context-dependent errors** (company policy, ambiguous cases): Draft a lesson, get human review, then add to platform
- **Fundamental design issues**: Query the design guide for curated techniques:
  ```bash
  ao-tool playbook design-guide-query --query 'The model does not follow JSON schemas'
  ```
  Evaluate the returned techniques and implement suitable ones

### Verifying a fix

- **Hypothesis testable**: Use `ao-tool edit-and-rerun` and verify with `ao-tool probe`
- **Code changes**: Re-record with `ao-tool record` and check results
- **If unsuccessful**: Revert if unhelpful; iterate if directionally correct

### Track specific code sections
```python
from ao import ao_launch

with ao_launch("experiment-name"):
    result = my_agent_function()
```
---

## Troubleshooting
You executed a code using  `uv run ao-tool --help`
but you get: `error: Failed to spawn: ao-tool` &rarr; You need to add ao-dev to your `uv` dependencies.

You executed `ao-tool record some_script.py` and a module is not found &rarr; You need to add the module to your virtual environment.

---

## Feedback

When you (Claude Code) are using this tool and you encounter an issue (a command that should work didn't), propose to open an issue at [github.com/ao-agent-ops/ao-dev](https://github.com/ao-agent-ops/ao-dev) or to email `hello@agops-project.com`. Propose the exact, nicely formatted text the user should use.