# Architecture

This page provides a high-level overview of AO's architecture and how its components work together.

## System Overview

AO consists of three main processes that work together:

![Processes Overview](../media/processes.png)

### 1. User Program (Green)

The user launches their program with `ao-record script.py`. This feels exactly like running `python script.py` - same terminal I/O, same crash behavior, and debugger support.

**Key point:** User code runs completely unmodified. AO uses monkey patching to intercept LLM calls and content-based matching to detect dataflow edges.

**Components:**

- **Agent Runner** (`agent_runner.py`) - Wraps the user's Python command. Sets up the environment, connects to the server, applies monkey patches, then executes the user's program.
- **Monkey Patching** (`monkey_patching/`) - Intercepts LLM API calls to record inputs/outputs.
- **String Matching** (`string_matching.py`) - Detects dataflow edges using content-based matching.

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

## Content-Based Edge Detection

AO detects dataflow between LLM calls using content-based matching:

1. **Store outputs**: When an LLM call completes, all text strings from the response are stored in an in-memory registry
2. **Match inputs**: When a new LLM call is made, we check if any previously stored output strings appear as substrings in the input
3. **Create edges**: If a match is found, an edge is created from the source node to the current node

This approach is simple and robust:
- User code runs completely unmodified
- Works with any LLM library that uses httpx/requests
- No risk of crashing user code

## Execution Flow

1. User runs `ao-record script.py`
2. Agent runner sets up environment (random seeds, server connection)
3. Agent runner connects to server (starts it if needed)
4. Monkey patches are applied to LLM libraries
5. User code executes unmodified
6. LLM calls are intercepted and reported to server
7. Content-based matching detects dataflow edges
8. Server builds dataflow graph
9. UI displays the graph in real-time

## Module Organization

```
src/
├── cli/                    # Command-line interface
│   ├── ao_record.py       # Main launch command
│   ├── ao_server.py       # Server management
│   └── ao_config.py       # Configuration
├── runner/                 # Runtime execution
│   ├── agent_runner.py     # Main runner (setup + execution)
│   ├── string_matching.py  # Content-based edge detection
│   ├── context_manager.py  # Session management
│   └── monkey_patching/    # API interception
│       ├── apply_monkey_patches.py
│       └── patches/        # Per-API patches
├── server/                 # Core server
│   ├── main_server.py      # Main server logic
│   ├── file_watcher.py     # Git versioning
│   └── database_manager.py # Caching/storage + content registry
└── user_interfaces/        # UI components
    ├── vscode_extension/   # VS Code extension
    └── web_app/            # Standalone web app
```

## Next Steps

- [Server internals](server.md) - Deep dive into the development server
- [Edge detection](edge-detection.md) - How dataflow edges are detected
- [API patching](api-patching.md) - How LLM APIs are intercepted
