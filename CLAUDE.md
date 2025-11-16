# Agent Copilot - LLM Dataflow Graph System

Agent Copilot is a development tool that creates interactive dataflow graphs of LLM calls, enabling visualization, editing, and debugging of data flow in agentic AI applications.

## Quick File References

Core system files:
- @src/server/ast_transformer.py - AST rewrites for taint propagation
- @src/server/file_watcher.py - Automatic file monitoring and recompilation
- @src/runner/taint_wrappers.py - Taint-aware data types for tracking provenance
- @src/runner/launch_scripts.py - Runtime environment setup
- @src/runner/ast_rewrite_hook.py - Import hook ensuring `.pyc` availability
- @src/runner/monkey_patching/patches/openai_patches.py - LLM API interception example
- @src/runner/README.md - Overall runner system documentation

## System Overview

The system creates dataflow graphs through three integrated layers:
1. **AST Transformation**: Rewrites Python code to propagate "taint" through all operations
2. **Monkey Patching**: Intercepts LLM API calls to build graph nodes and edges
3. **Taint Tracking**: Traces data provenance from LLM outputs through program execution

## How It Works

1. **Pre-execution**: @src/server/file_watcher.py monitors files and triggers AST rewrites via @src/server/ast_transformer.py
2. **Runtime Setup**: @src/runner/launch_scripts.py registers taint functions and establishes server connection
3. **Import Hook**: @src/runner/ast_rewrite_hook.py ensures AST-rewritten `.pyc` files exist before module imports
4. **Execution**: User code runs with rewritten `.pyc` files that automatically propagate taint through operations
5. **LLM Interception**: @src/runner/monkey_patching/patches/ intercept API calls to build dataflow graph
6. **Visualization**: Interactive graph shows LLM calls as nodes and data dependencies as edges

## Installation & Setup

## Key Commands

```bash
# Installation
source ~/miniforge3/bin/activate aco && pip install -e .

# Running (replace python with aco-launch)
aco-launch script.py
~/miniforge3/envs/aco/bin/python -m aco.cli.aco_launch script.py  # For Claude Code

# Server management
aco-server start/stop/restart/clear/logs

# Testing
python -m pytest -v tests/taint/  # Test taint propagation specifically
```

## Project Structure

- @src/cli/ - Command-line interface (`aco-launch`, `aco-server`)
- @src/server/ - Core analysis server, AST transformation, file watching
- @src/runner/ - User program execution, monkey patching, taint wrappers
- @src/user_interfaces/ - VS Code extension and web app
- @tests/taint/ - Taint propagation unit tests
- @example_workflows/ - Various AI workflow examples

## Code Style & Guidelines

- **Follow monkey patching pattern** from @src/runner/monkey_patching/patches/openai_patches.py

## Do Not

- **Do NOT** overcomplicate the system. Simplicity is a core concern of the code base. Instead of writing complicated code, tell the user what you want to change, why and explain how this fits into the rest of the code base.
- Remain critical and skeptical about my thinking at all times. Maintain consistent intellectual standards throughout our conversation. Don’t lower your bar for evidence or reasoning quality just because we’ve been talking longer or because I seem frustrated. If I’m making weak arguments, keep pointing that out even if I’ve made good ones before.

## Caveats

- **aco and agops** You will sometimes see aco (short for agent copilot) and agops (short for agent ops). They mean to denote the same thing (an abbreviation of the project name).
