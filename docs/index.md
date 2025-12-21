# Agent Copilot

Agent Copilot is a development tool that creates interactive dataflow graphs of LLM calls, enabling visualization, editing, and debugging of data flow in agentic AI applications.

## Overview

Agent Copilot allows you to:

- **Visualize LLM call chains** - See how data flows between LLM calls in your application
- **Edit inputs and outputs** - Modify LLM call inputs/outputs and re-run with changes
- **Debug dataflow** - Track how LLM outputs propagate through your code
- **Cache LLM calls** - Speed up development by caching and replaying LLM responses

## User Workflow

We assume you have coded your workflow in Python, i.e., you run it with something like:

```bash
python -m foo.bar
ENV_VAR=5 python script.py --some-flag
```

All you change is the Python command. Whenever you want to develop with Agent Copilot, run:

```bash
aco-launch -m foo.bar
ENV_VAR=5 aco-launch script.py --some-flag
```

This feels *exactly* the same as running Python but also analyzes your code and populates the VS Code extension:

- Program prints/reads to/from the same terminal, crashes the same, etc.
- You can use the VS Code debugger normally

## Quick Start

1. [Install Agent Copilot](getting-started/installation.md)
2. [Run your first example](getting-started/quickstart.md)
3. [Learn the CLI commands](user-guide/cli-commands.md)

## Further Resources

- [Join our Discord server](https://discord.gg/fjsNSa6TAh)
- [GitHub Repository](https://github.com/yourusername/agent-copilot)
