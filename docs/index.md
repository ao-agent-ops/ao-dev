# AO

The trace of an agent executing a task is effectively a [DAG](https://en.wikipedia.org/wiki/Directed_acyclic_graph), where the nodes are LLM or tool calls, and the edges are virtual connections representing data that flows from one node to another. However, current AgentOps platforms do not represent agentic traces like this, making it hard to understand where and why an agent failed to complete a task.

AO is a development tool that creates interactive dataflow graphs of agent traces, enabling visualization, editing, and debugging of data flow in agentic systems – **with *zero* code changes**.

<video controls width="100%">
  <source src="assets/videos/example.mp4" type="video/mp4">
  Your browser does not support the video tag.
</video>

## Overview

AO goes beyond being a simple observability tool:

- **Visualize agent traces as a DAG** - See how data flows between LLM and tool calls in your application
- **Edit inputs and outputs** - Modify LLM and tool call inputs/outputs and **re-run** with changes, where previous nodes in the DAG are cached
- **Debug dataflow** - Track how LLM outputs propagate through your code
- **Automatically improve any agent** - AO is also an MCP tool, enabling observaility and fast debugging for your favorite coding agent like [Claude Code](https://claude.com/product/claude-code)

## How to use

We assume you have coded your workflow in Python, i.e., you run it like this:

```bash
python -m agent.run
ENV_VAR=5 python agent/run.py --some-flag
```

All you change is the Python command. Whenever you want to develop with AO, run:

```bash
ao-record -m agent.run
ENV_VAR=5 ao-record agent/run.py --some-flag
```

You can set a custom run name using `--run-name`:

```bash
ao-record --run-name "my-experiment" agent/run.py
```

This feels *exactly* the same as running Python but also analyzes your code and populates our [VS Code extension](https://google.com):

- Program prints/reads to/from the same terminal, crashes the same, etc.
- You can use the VS Code debugger normally

For running evaluations or batch processing, use the `ao_subrun` context manager to create separate traces for each sample:

```
from ao import ao_subrun

for sample in samples:
    with ao_subrun(f"sample-{sample.id}"):
        result = evaluate(sample)
```

## Quick Start

1. [Install AO](getting-started/installation.md)
2. [Run your first example](getting-started/quickstart.md)
3. [Learn the CLI commands](user-guide/cli-commands.md)

## Further Resources

- [Join our Discord server](https://discord.gg/fjsNSa6TAh)
- [GitHub Repository](https://github.com/agent-ops-project/agops-platform)
