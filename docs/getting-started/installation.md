# Installation

## Prerequisites

- Python 3.10 or higher (Python 3.13 recommended)

## Quick Install

```bash
pip install ao
```

## Verifying Installation

After installation, verify that the CLI commands are available:

```bash
ao-record --help
ao-server --help
```

## Developer Installation

If you are contributing to AO, clone the repository and install with development dependencies:

```bash
pip install -e ".[dev]"
```

For development with documentation building:

```bash
pip install -e ".[dev,docs]"
```

### IDE Linter Configuration

Some Python linters may incorrectly report that modules inside the codebase can't be found. Run the following in the project root to resolve this:

```bash
ln -s src ao
```

## Next Steps

- [Run your first example](quickstart.md)
- [Learn the CLI commands](../user-guide/cli-commands.md)
