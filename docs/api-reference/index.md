# API Reference

This section provides auto-generated API documentation from the AO source code.

## Overview

AO's Python API is organized into several modules:

### CLI Modules

- [**CLI**](cli.md) - Command-line interface entry points (`ao-record`, `ao-server`, `ao-config`)

## Module Structure

```
ao/
├── cli/                    # Command-line tools
│   ├── ao_record.py       # Main launch command
│   ├── ao_server.py       # Server management
│   └── ao_config.py       # Configuration tool
├── runner/                 # Runtime execution
│   ├── string_matching.py  # Content-based edge detection
│   ├── context_manager.py  # Session management
│   └── monkey_patching/    # API interception
└── server/                 # Core server
    ├── file_watcher.py     # Git versioning
    ├── database_manager.py # Caching and content registry
    └── main_server.py      # Main server
```

## Using the API

Most users interact with AO through the CLI commands. However, you can also use the Python API directly:

### Context Manager for Subruns

```python
from ao import launch

with launch("my-run"):
    # Your LLM code here
    pass
```

## Next Steps

- [CLI Reference](cli.md)
