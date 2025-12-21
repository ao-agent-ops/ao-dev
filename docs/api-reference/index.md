# API Reference

This section provides auto-generated API documentation from the Agent Copilot source code.

## Overview

Agent Copilot's Python API is organized into several modules:

### CLI Modules

- [**CLI**](cli.md) - Command-line interface entry points (`aco-launch`, `aco-server`, `aco-config`)

### Core Runtime

- [**Taint Wrappers**](taint-wrappers.md) - Taint-aware data types for tracking data provenance
- [**AST Transformer**](ast-transformer.md) - AST rewriting for taint propagation

## Module Structure

```
aco/
├── cli/                    # Command-line tools
│   ├── aco_launch.py       # Main launch command
│   ├── aco_server.py       # Server management
│   └── aco_config.py       # Configuration tool
├── runner/                 # Runtime execution
│   ├── taint_wrappers.py   # Taint-aware types
│   ├── context_manager.py  # Session management
│   └── monkey_patching/    # API interception
└── server/                 # Core server
    ├── ast_transformer.py  # AST rewriting
    ├── file_watcher.py     # File monitoring
    └── develop_server.py   # Main server
```

## Using the API

Most users interact with Agent Copilot through the CLI commands. However, you can also use the Python API directly:

### Context Manager for Subruns

```python
from aco.runner.context_manager import aco_launch

with aco_launch("my-run"):
    # Your LLM code here
    pass
```

### Taint Wrappers

Taint wrappers are automatically applied when using `aco-launch`. You generally don't need to create them manually, but understanding them helps with debugging:

```python
from aco.runner.taint_wrappers import TaintStr, get_taint_origins

# Check if a value is tainted
origins = get_taint_origins(some_value)
if origins:
    print(f"Value came from: {origins}")
```

## Next Steps

- [CLI Reference](cli.md)
- [Taint Wrappers Reference](taint-wrappers.md)
- [AST Transformer Reference](ast-transformer.md)
