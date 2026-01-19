---
name: ao
description: ao helps you develop and maintain adaptable agentic systems. It extends Claude Code with context-optimized observability, accelerated A/B testing, a curated playbook of agent development techniques, and dynamic runtime lesson injection. Use when actively developing or improving agentic systems.
---

# ao

## Overview

- **Integrated Observability** – Record agent traces as dataflow graphs with zero code changes
- **Accelerated A/B Testing** – Edit node inputs/outputs and rerun to see how changes propagate
- **Lessons** – Inject learned lessons into agent context dynamically at runtime
- **Design Playbook** – Query curated agent development techniques

---

## Integrated Observability

Record agent execution as a graph where nodes are LLM/tool calls and edges are data dependencies.

### Record a script
```bash
ao-tool record agent.py                       # Start recording, return immediately
ao-tool record agent.py --wait                # Block until script completes
ao-tool record agent.py --wait --timeout 60   # Wait with 60s timeout
ao-tool record -m my_module                   # Run as Python module
ao-tool record --run-name "Eval run" agent.py # Name the run
```

### Inspect a session
```bash
ao-tool probe <session_id>                    # Full session with all nodes
ao-tool probe <session_id> --topology         # Graph structure only
ao-tool probe <session_id> --node <node_id>   # Single node with I/O
ao-tool probe <session_id> --nodes <id1,id2>  # Multiple nodes
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

TODO: Document playbook query API and usage patterns.

---

## Workflow Recipes

### Setup

**Always** integrate the lessons API first:
```python
# Example code here
```

### Debugging a failing agent

1. **Set up evaluation criteria**
   - *Correctness*: Add verification code (test cases, state checks, exception handling)
   - *Cost/latency*: Query with `ao-tool experiments --regex ...`

2. **Capture execution**: `ao-tool record agent.py`

3. **Locate the error** using `ao-tool probe`:
   - Start with topology: `ao-tool probe <session_id> --topology`
   - Small graphs (<10 nodes): dump everything with `ao-tool probe <session_id>`
   - Large graphs: traverse nodes via `ao-tool probe <session_id> --node <node_id>`

### Implementing a fix

- **Simple, generic errors**: Modify the system prompt directly
- **Context-dependent errors** (company policy, ambiguous cases): Draft a lesson, get human review, then add to platform
- **Fundamental issues**: Query the playbook, evaluate proposals, implement suitable ones

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

## Feedback

Found a design issue or missing feature? Open an issue at [github.com/ao-agent-ops/ao-dev](https://github.com/ao-agent-ops/ao-dev) or email `hello@agops-project.com`.