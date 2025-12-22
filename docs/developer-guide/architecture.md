# Architecture

This page provides a high-level overview of AO's architecture and how its components work together.

## System Overview

AO consists of three main processes that work together:

![Processes Overview](../assets/images/processes.png)

### 1. User Program (Green)

The user launches their program with `ao-record script.py`. This feels exactly like running `python script.py` - same terminal I/O, same crash behavior, and debugger support.

**Components:**

- **Orchestrator** (`develop_shim.py`) - Manages the lifecycle of the runner process. Handles restart commands from the UI.
- **Runner** - Executes the actual Python program with monkey patches and AST rewrites applied.

### 2. Development Server (Blue)

The core analysis engine that receives events from the user process and updates the UI.

**Responsibilities:**

- Receives LLM call events from the runner
- Builds and maintains the dataflow graph
- Manages LLM call caching
- Handles user edits to inputs/outputs
- Controls the UI

**Communication:** All messages flow through a TCP socket (default port: 5959).

### 3. UI (Red)

The VS Code extension (or web app) that displays the dataflow graph and provides interactive controls.

**Features:**

- Visualizes the dataflow graph
- Allows editing of LLM inputs/outputs
- Triggers re-runs with modifications
- Shows run history

## Data Flow Architecture

### How Taint Tracking Works

AO tracks data flow using a "taint" system:

1. **LLM Output Tainting** - When an LLM produces output, it's wrapped in a taint-aware type that records the LLM call ID
2. **Taint Propagation** - As data flows through the program, taint information propagates through operations
3. **Edge Detection** - When tainted data reaches another LLM call, an edge is added to the dataflow graph

### Two Mechanisms for Taint Propagation

1. **Monkey Patching** - Intercepts LLM API calls to:
   - Record inputs and outputs
   - Wrap outputs with taint information
   - Report events to the server

2. **AST Rewriting** - Rewrites Python code to propagate taint through:
   - Third-party library calls
   - String formatting operations
   - Built-in functions

## Execution Flow

![Execution Flow](../assets/images/develop_spawn.png)

1. User runs `ao-record script.py`
2. Orchestrator spawns the runner process
3. Runner establishes connection to the server
4. Monkey patches and AST rewrites are applied
5. User code executes with full tracing
6. LLM calls are intercepted and reported to server
7. Server builds dataflow graph
8. UI displays the graph in real-time

## Module Organization

```
src/
├── cli/                    # Command-line interface
│   ├── ao_record.py       # Main launch command
│   ├── ao_server.py       # Server management
│   └── ao_config.py       # Configuration
├── runner/                 # Runtime execution
│   ├── develop_shim.py     # Orchestrator
│   ├── launch_scripts.py   # Runner bootstrap
│   ├── taint_wrappers.py   # Taint-aware types
│   ├── context_manager.py  # Session management
│   └── monkey_patching/    # API interception
│       ├── apply_monkey_patches.py
│       └── patches/        # Per-API patches
├── server/                 # Core server
│   ├── develop_server.py   # Main server logic
│   ├── ast_transformer.py  # AST rewriting
│   ├── file_watcher.py     # File monitoring
│   └── database_manager.py # Caching/storage
└── user_interfaces/        # UI components
    ├── vscode_extension/   # VS Code extension
    └── web_app/            # Standalone web app
```

## Next Steps

- [Server internals](server.md) - Deep dive into the development server
- [Taint tracking](taint-tracking.md) - How data flow is tracked
- [API patching](api-patching.md) - How LLM APIs are intercepted
