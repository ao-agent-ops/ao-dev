# CLI Commands

AO provides three main CLI commands for running and managing your LLM applications.

## ao-record

The primary command for running Python scripts with AO analysis.

### Basic Usage

```bash
# Run a script
ao-record script.py

# Run a script with arguments
ao-record script.py --arg1 value1 --arg2 value2

# Run a module
ao-record -m mypackage.mymodule

# Run with environment variables
ENV_VAR=value ao-record script.py
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
ao-record my_agent.py

# Run a module from a package
ao-record -m agents.research_agent

# Run with a custom run name
ao-record --run-name "experiment-v1" my_agent.py

# Pass arguments to your script
ao-record my_agent.py --model gpt-4 --temperature 0.7
```

## ao-server

Manage the AO development server.

### Commands

```bash
# Start the server
ao-server start

# Stop the server
ao-server stop

# Restart the server (useful after code changes)
ao-server restart

# Clear all recorded runs and cached LLM calls
ao-server clear

# View server logs
ao-server logs
```

### Notes

- The server automatically starts when you run `ao-record` if it's not already running
- If you make changes to server code, run `ao-server restart` to apply them
- Server logs are stored in `~/.cache/ao/logs/server.log`

### Troubleshooting

Check if the server process is running:

```bash
ps aux | grep develop_server.py
```

Check which processes are using the server port:

```bash
lsof -i :5959
```

## ao-config

Configure AO settings interactively.

### Usage

```bash
ao-config
```

This launches an interactive configuration wizard that prompts you for:

- **Project root directory** - The root of your Python project
- **Database URL** - Configuration for result caching

### When to Use

Run `ao-config` when:

- Setting up AO for a new project
- Changing the project root directory
- Configuring database settings for caching

!!! tip "Project Root"
    For some example workflows, you may need to set the project root to the example's directory. Run `ao-config` and set it to the root of the example repo.

## Environment Variables

AO respects the following environment variables:

| Variable | Description |
|----------|-------------|
| `AO_SESSION_ID` | Current session identifier |
| `AO_ENABLE_TRACING` | Enable/disable tracing |
| `AO_SERVER_HOST` | Server host (default: localhost) |
| `AO_SERVER_PORT` | Server port (default: 5959) |
| `AO_SEED` | Random seed for reproducibility |

## Next Steps

- [Learn about the VS Code extension](vscode-extension.md)
- [Create subruns for batch processing](subruns.md)
