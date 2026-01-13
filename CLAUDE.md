# AO - LLM Dataflow Graph System

AO is a development tool that creates interactive dataflow graphs of LLM calls, enabling visualization, editing, and debugging of data flow in agentic AI applications. Each node in the data flow graph is an LLM or tool call and edges denote the output of one LLM/tool call forming part of the input of another.

## Edit & Rerun

The core goal is **interactive debugging of LLM workflows**:
1. Run your script once to capture the dataflow graph
2. Inspect any node's input/output in the UI
3. Edit an LLM's input or output directly
4. Rerun to see how changes propagate through the graph

On rerun, cached outputs are returned for unchanged inputs, and edited values are respected. This enables rapid iteration without re-calling LLMs unnecessarily.

## Quick File References

VSCode extension files:
- @src/user_interfaces/vscode_extension/src/ – Contains relevant source code for the extensions.

Core system files:
- @src/server/main_server.py - Manages the server that interfaces user script runner and extensions/UIs
- @src/server/database_manager.py - Manages communication with the database and content registry for edge detection
- @src/server/file_watcher.py - Git versioning for code snapshots
- @src/runner/agent_runner.py - Runtime environment setup
- @src/runner/string_matching.py - Content-based edge detection algorithm
- @src/runner/monkey_patching/patches/httpx_patch.py - LLM API interception example
- @src/runner/README.md - Overall runner system documentation

## How It Works

1. **Runtime Setup**: @src/runner/agent_runner.py establishes server connection and applies monkey patches
2. **User Code Runs Unmodified**: No AST rewrites - user code executes normally
3. **LLM Interception**: @src/runner/monkey_patching/patches/ intercept API calls (httpx, requests, etc.)
4. **Edge Detection**: @src/runner/string_matching.py checks if previous outputs appear in current input
5. **Visualization**: Interactive graph shows LLM calls as nodes and content matches as edges

## Installation & Setup

## Key Commands

```bash
# Installation
source ~/miniforge3/bin/activate ao && pip install -e .

# Running (replace python with ao-record)
ao-record script.py
~/miniforge3/envs/ao/bin/python -m ao.cli.ao_record script.py  # For Claude Code

# Server management
ao-server start/stop/restart/clear/logs

# Testing
python -m pytest -v tests/billable/  # Tests that make LLM API calls
```

## Project Structure

- @src/cli/ - CLI tools (`ao-record`, `ao-server`, `ao-config`)
- @src/common/ - Shared utilities (config, constants, logger, utils)
- @src/server/ - Core server (main_server, file_watcher, database_manager)
- @src/runner/ - Runtime execution (agent_runner, string_matching, context_manager)
- @src/runner/monkey_patching/ - API interception (patches/, api_parsers/)
- @src/user_interfaces/ - VS Code extension and web app
- @tests/billable/ - Tests that make LLM API calls
- @example_workflows/ - AI workflow examples (bird-bench, human_eval, swe_bench, debug_examples, etc.)
- @docs/ - Documentation for mkdocs site

## Do Not

- **Do NOT** overcomplicate the system. Simplicity is a core concern of the code base. When you make changes, explain me why this is the most straight-forward way to implement something and how it fits into the rest of the code base and (if applicable) matches existing patterns.
- **Do NOT** consider backwards compatability. The code has no users yet, which allows you to write cleaner, more concise code.
- Remain critical and skeptical about my thinking at all times. Maintain consistent intellectual standards throughout our conversation. Don't lower your bar for evidence or reasoning quality just because we've been talking longer or because I seem frustrated. If I'm making weak arguments, keep pointing that out even if I've made good ones before.
