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
python -m pytest -k "test_cache"
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

## Special Test Cases

### test_api_calls.py

For API call tests, the user program executes as a replay by the server. To see the output:

```bash
ao-server logs
```

This shows the output of the user program, including any crash information.

### Edge Detection Tests

Tests for content-based edge detection verify that dataflow edges are correctly detected when LLM outputs appear in subsequent LLM inputs:

```bash
python -m pytest tests/billable/ -k "edge"
```

## Writing New Tests

### Standard Test

```python
# tests/test_my_feature.py
import pytest

def test_my_feature():
    # Your test code
    assert result == expected
```

### API Patch Test

API patch tests are in `tests/billable/` since they typically make actual API calls. For unit testing patches without API calls, use mocks:

```python
# tests/billable/test_caching.py
def test_llm_caching():
    # These tests verify that LLM calls are cached correctly
    # See existing tests for patterns
    pass
```

### Edge Detection Test

To test that edges are correctly detected:

```python
def test_edge_detection():
    # LLM call 1 - output contains "42"
    response1 = llm_call("Output the number 42")

    # LLM call 2 - input contains "42" from previous output
    response2 = llm_call(f"Add 1 to {response1}")

    # Verify an edge was created between the two nodes
    # Check the graph topology in the session
    pass
```

## Test Fixtures

Common test helpers are defined in `tests/utils.py`, including:

- `setup_test_session` - Helper to create database records for testing

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

## Next Steps

- [Architecture](architecture.md) - Understand the system design
- [API patching](api-patching.md) - Write patches for new LLM APIs
