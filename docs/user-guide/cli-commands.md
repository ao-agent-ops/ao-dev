# CLI Commands

Agent Copilot provides three main CLI commands for running and managing your LLM applications.

## aco-launch

The primary command for running Python scripts with Agent Copilot analysis.

### Basic Usage

```bash
# Run a script
aco-launch script.py

# Run a script with arguments
aco-launch script.py --arg1 value1 --arg2 value2

# Run a module
aco-launch -m mypackage.mymodule

# Run with environment variables
ENV_VAR=value aco-launch script.py
```

### Options

| Option | Description |
|--------|-------------|
| `-m, --module` | Run as a Python module instead of a script |
| `--config-file` | Path to configuration file |
| `--run-name` | Name for this run (for organizing in the UI) |
| `--project-root` | Override the project root directory |

### Examples

```bash
# Run a simple script
aco-launch my_agent.py

# Run a module from a package
aco-launch -m agents.research_agent

# Run with a custom run name
aco-launch --run-name "experiment-v1" my_agent.py

# Pass arguments to your script
aco-launch my_agent.py --model gpt-4 --temperature 0.7
```

## aco-server

Manage the Agent Copilot development server.

### Commands

```bash
# Start the server
aco-server start

# Stop the server
aco-server stop

# Restart the server (useful after code changes)
aco-server restart

# Clear all recorded runs and cached LLM calls
aco-server clear

# View server logs
aco-server logs
```

### Notes

- The server automatically starts when you run `aco-launch` if it's not already running
- If you make changes to server code, run `aco-server restart` to apply them
- Server logs are stored in `~/.cache/agent-copilot/logs/server.log`

### Troubleshooting

Check if the server process is running:

```bash
ps aux | grep develop_server.py
```

Check which processes are using the server port:

```bash
lsof -i :5959
```

## aco-config

Configure Agent Copilot settings interactively.

### Usage

```bash
aco-config
```

This launches an interactive configuration wizard that prompts you for:

- **Project root directory** - The root of your Python project
- **Database URL** - Configuration for result caching

### When to Use

Run `aco-config` when:

- Setting up Agent Copilot for a new project
- Changing the project root directory
- Configuring database settings for caching

!!! tip "Project Root"
    For some example workflows, you may need to set the project root to the example's directory. Run `aco-config` and set it to the root of the example repo.

## Environment Variables

Agent Copilot respects the following environment variables:

| Variable | Description |
|----------|-------------|
| `AGENT_COPILOT_SESSION_ID` | Current session identifier |
| `AGENT_COPILOT_ENABLE_TRACING` | Enable/disable tracing |
| `AGENT_COPILOT_SERVER_HOST` | Server host (default: localhost) |
| `AGENT_COPILOT_SERVER_PORT` | Server port (default: 5959) |
| `ACO_SEED` | Random seed for reproducibility |

## Next Steps

- [Learn about the VS Code extension](vscode-extension.md)
- [Create subruns for batch processing](subruns.md)
