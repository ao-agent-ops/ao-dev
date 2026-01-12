# API Reference

This section provides auto-generated API documentation from the AO source code.

## Overview

AO's Python API is organized into several modules:

### CLI Modules

- [**CLI**](cli.md) - Command-line interface entry points (`ao-record`, `ao-server`, `ao-config`)

### Core Runtime

- [**AST Transformer**](ast-transformer.md) - AST rewriting for taint propagation

## Module Structure

```
ao/
├── cli/                    # Command-line tools
│   ├── ao_record.py       # Main launch command
│   ├── ao_server.py       # Server management
│   └── ao_config.py       # Configuration tool
├── runner/                 # Runtime execution
│   ├── taint_containers.py # Taint tracking containers
│   ├── context_manager.py  # Session management
│   └── monkey_patching/    # API interception
└── server/                 # Core server
    ├── ast_transformer.py  # AST rewriting
    ├── file_watcher.py     # File monitoring
    └── main_server.py   # Main server
```

## Using the API

Most users interact with AO through the CLI commands. However, you can also use the Python API directly:

### Context Manager for Subruns

```
from ao import launch

with launch("my-run"):
    # Your LLM code here
    pass
```

## Next Steps

- [CLI Reference](cli.md)
- [AST Transformer Reference](ast-transformer.md)
