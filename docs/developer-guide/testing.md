# Testing

This guide covers how to run AO's test suite and write new tests.

## Running Tests

### Basic Test Run

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_specific.py

# Run tests matching a pattern
python -m pytest -k "test_taint"
```

### Taint Propagation Tests

The taint propagation tests verify that taint flows correctly through various operations:

```bash
python -m pytest -v tests/non_billable/taint/
```

## Test Categories

### Non-Billable Tests

Tests that don't make actual LLM API calls (no cost):

```bash
python -m pytest tests/non_billable/
```

### Billable Tests

Tests that make actual LLM API calls (costs money):

```bash
python -m pytest tests/billable/
```

### Taint Tests

Tests specifically for taint propagation through different operations:

```bash
python -m pytest tests/non_billable/taint/
```

## Special Test Cases

### test_api_calls.py

For API call tests, the user program executes as a replay by the server. To see the output:

```bash
ao-server logs
```

This shows the output of the user program, including any crash information.

### Taint General Function Tests

Tests in `tests/non_billable/taint/` require AST rewriting to test taint propagation through operations.

**Why special?**

- Pytest normally compiles test files from source without our AST rewrites
- Tests need the AST-rewritten code to verify taint propagation
- Solution: Use the `@with_ast_rewriting` decorator from `tests/utils.py`

**How it works:**

The `@with_ast_rewriting` decorator (or `@with_ast_rewriting_class` for entire test classes):

1. Extracts the test function's source code at runtime
2. Applies AST transformation for taint tracking
3. Executes the transformed code inline
4. Sets up the taint environment (TAINT_DICT, TAINT_STACK, builtins)

**Example usage:**

```python
from tests.utils import with_ast_rewriting

@with_ast_rewriting
def test_json_loads_taint():
    result = json.loads(tainted_data)
    assert get_taint(result) != []
```

This approach provides:

- Accurate testing of actual AST rewrites
- Per-test granularity in results
- Standard pytest integration (no separate process)

## Writing New Tests

### Standard Test

```
# tests/test_my_feature.py
import pytest

def test_my_feature():
    # Your test code
    assert result == expected
```

### Taint Propagation Test

Taint tests verify that taint flows correctly through operations. See existing tests in `tests/non_billable/taint/` for examples:

```
# tests/non_billable/taint/unit/test_taint_str.py
import builtins
from ao.server.taint_ops import get_taint

def test_string_concatenation():
    # Set up taint tracking
    builtins.TAINT_DICT[id("hello")] = ("hello", ["origin1"])

    # Perform operation (in real tests, AST rewriting handles this)
    result = "hello" + " world"

    # Verify taint propagated
    taint = get_taint(result)
    assert "origin1" in taint
```

### API Patch Test

API patch tests are in `tests/billable/` since they typically make actual API calls. For unit testing patches without API calls, use mocks:

```
# tests/billable/test_caching.py
def test_llm_caching():
    # These tests verify that LLM calls are cached correctly
    # See existing tests for patterns
    pass
```

## Test Fixtures

Common test helpers are defined in `tests/utils.py`, including:

- `with_ast_rewriting` - Decorator for tests that need AST transformation
- `with_ast_rewriting_class` - Class decorator for test classes
- `setup_test_session` - Helper to create database records for testing
- `cleanup_taint_db` - Clean up taint information between tests

## Debugging Failed Tests

### View Server Logs

```bash
ao-server logs
```

### Run with Debug Output

```bash
python -m pytest -v --tb=long tests/test_failing.py
```

### Run Single Test

```bash
python -m pytest -v tests/test_file.py::test_specific_function
```

## CI/CD Considerations

The test suite runs in GitHub Actions. Key considerations:

- Tests must be deterministic (use fixed random seeds)
- API tests should use mocks or replay mode
- Taint tests require the full `ao-record` environment

## Next Steps

- [Architecture](architecture.md) - Understand the system design
- [API patching](api-patching.md) - Write patches for new LLM APIs
