# API Reference

This section provides auto-generated API documentation from the AO source code.

## Overview

AO's Python API is organized into several modules:

### CLI Modules

- [**CLI**](cli.md) - Command-line interface entry points (`ao-record`, `ao-server`, `ao-config`)

### Core Runtime

- [**Taint Wrappers**](taint-wrappers.md) - Taint-aware data types for tracking data provenance
- [**AST Transformer**](ast-transformer.md) - AST rewriting for taint propagation

## Module Structure

```
ao/
├── cli/                    # Command-line tools
│   ├── ao_record.py       # Main launch command
│   ├── ao_server.py       # Server management
│   └── ao_config.py       # Configuration tool
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

Most users interact with AO through the CLI commands. However, you can also use the Python API directly:

### Context Manager for Subruns

```
from ao.runner.context_manager import ao_record

with ao_record("my-run"):
    # Your LLM code here
    pass
```

### Taint Wrappers

Taint wrappers are automatically applied when using `ao-record`. You generally don't need to create them manually, but understanding them helps with debugging:

```
from ao.runner.taint_wrappers import TaintStr, get_taint_origins

# Check if a value is tainted
origins = get_taint_origins(some_value)
if origins:
    print(f"Value came from: {origins}")
```

## Next Steps

- [CLI Reference](cli.md)
- [Taint Wrappers Reference](taint-wrappers.md)
- [AST Transformer Reference](ast-transformer.md)
