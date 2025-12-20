# Installation

## Prerequisites

- Python 3.10 or higher (Python 3.13 recommended)
- Node.js (for the VS Code extension)
- conda or pip for package management

## Quick Install

### Create a Python Environment

If you're starting from a clean sheet, create a blank conda environment and activate it:

```bash
conda create -n aco python=3.13 -y && conda activate aco
```

### Install the Package

```bash
pip install -e .
```

### Build the UI Components

Because the extension is not yet packaged, you need to install UI dependencies:

```bash
cd src/user_interfaces && npm install
npm run build:all
```

## Developer Installation

If you are contributing to Agent Copilot, install the development dependencies:

```bash
pip install -e ".[dev]"
pre-commit install
cd src/user_interfaces && npm run build:all
```

### IDE Linter Configuration

Some Python linters may incorrectly report that modules inside the codebase can't be found. Run the following in the project root to resolve this:

```bash
ln -s src aco
```

## Verifying Installation

After installation, verify that the CLI commands are available:

```bash
aco-launch --help
aco-server --help
```

## Next Steps

- [Run your first example](quickstart.md)
- [Learn the CLI commands](../user-guide/cli-commands.md)
