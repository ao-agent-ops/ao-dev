# Claude Code Integration

AO integrates with [Claude Code](https://docs.anthropic.com/en/docs/claude-code) to accelerate agent development. Instead of manually inspecting logs or stepping through debuggers, Claude Code can directly query your agent's dataflow graph, understand what happened, and help you iterate faster.

![AO x Claude Code](../media/ao-x-cc.png)

## Why Use This Integration?

- **Keep context clean**: Agent runs produce verbose logs that quickly pollute Claude's context window. With `ao-tool`, Claude queries only the specific nodes it needs.
- **Structured access**: Claude gets structured JSON data (inputs, outputs, graph topology) rather than parsing raw logs.
- **Edit and rerun**: Claude can programmatically edit an LLM's input or output and trigger a rerun to test hypotheses.

## Setup

Run the interactive setup command:

```bash
ao-tool install-skill
```

This will:

1. Ask for your project directory (with tab-completion)
2. Copy the AO skill file to `.claude/skills/ao/SKILL.md`
3. Optionally add Bash permissions to `.claude/settings.local.json` so Claude can run `ao-tool` commands without prompts

After setup, restart Claude Code to load the new skill.

## Available Commands

Once set up, Claude Code can use these commands:

### Record an Agent Run

```bash
ao-tool record agent.py                    # Start recording, return immediately
ao-tool record --wait agent.py             # Block until script completes
ao-tool record --wait --timeout 60 agent.py  # Wait with 60s timeout
```

### Query Session State

```bash
# List recent experiments
ao-tool experiments --range :10

# Get graph topology (nodes and edges, no content)
ao-tool probe <session_id> --topology

# Get full node details
ao-tool probe <session_id> --node <node_id>

# Get truncated preview (20 char strings)
ao-tool probe <session_id> --node <node_id> --preview

# Filter keys with regex
ao-tool probe <session_id> --node <node_id> --key-regex "messages.*content"

# Only show input or output
ao-tool probe <session_id> --node <node_id> --input
ao-tool probe <session_id> --node <node_id> --output
```

### Edit and Rerun

```bash
# Edit output and rerun
ao-tool edit-and-rerun <session_id> <node_id> --output '{"content": "new response"}'

# Edit input and rerun
ao-tool edit-and-rerun <session_id> <node_id> --input '{"messages": [...]}'

# Create a new run instead of modifying in place
ao-tool edit-and-rerun <session_id> <node_id> --output '...' --as-new-run

# Wait for rerun to complete
ao-tool edit-and-rerun <session_id> <node_id> --output '...' --wait
```

### Other Commands

```bash
ao-tool terminate <pid>          # Stop a running process
```

## Workflow Examples

### Debug a Failing Agent

1. Claude records the agent: `ao-tool record agent.py --wait`
2. Inspects the graph: `ao-tool probe <session_id> --topology`
3. Examines the failing node: `ao-tool probe <session_id> --node <failing_node>`
4. Fixes and reruns: `ao-tool edit-and-rerun <session_id> <node_id> --output '...' --wait`

### A/B Test a Prompt Change

1. Run original: `ao-tool record agent.py --wait`
2. Inspect the node to edit: `ao-tool probe <session_id> --node <node_id>`
3. Create variant: `ao-tool edit-and-rerun <session_id> <node_id> --input '...' --as-new-run --wait`
4. Compare the two sessions

### Iterate on LLM Output

1. Run agent and find a suboptimal response
2. Edit the output to what you want: `ao-tool edit-and-rerun <session_id> <node_id> --output '...'`
3. See how downstream nodes react to the improved output
4. Use insights to improve your prompts

## Output Format

All `ao-tool` commands output JSON for easy parsing. Examples:

**Successful record:**
```json
{
  "status": "completed",
  "session_id": "abc-123",
  "exit_code": 0,
  "duration_seconds": 12.5
}
```

**Probe topology:**
```json
{
  "session_id": "abc-123",
  "nodes": [
    {"node_id": "node-1", "label": "GPT-4", "parent_ids": [], "child_ids": ["node-2"]}
  ],
  "edges": [
    {"source": "node-1", "target": "node-2"}
  ]
}
```

**Error:**
```json
{
  "status": "error",
  "error": "Session not found: xyz"
}
```
