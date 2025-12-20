# Testing

This guide covers how to run Agent Copilot's test suite and write new tests.

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
python -m pytest -v tests/taint/
```

## Test Categories

### Unit Tests

Standard pytest tests that don't require the server:

```bash
python -m pytest tests/unit/
```

### Integration Tests

Tests that require the full Agent Copilot environment:

```bash
python -m pytest tests/integration/
```

### Taint Tests

Tests specifically for taint propagation through different operations:

```bash
python -m pytest tests/taint/
```

## Special Test Cases

### test_api_calls.py

For API call tests, the user program executes as a replay by the server. To see the output:

```bash
aco-server logs
```

This shows the output of the user program, including any crash information.

### Taint General Function Tests

Tests in `taint/general_functions` have a special setup because they rely on AST rewriting.

**Why special?**

- Pytest normally ignores `.pyc` files and compiles from source
- Our tests need the AST-rewritten `.pyc` files
- Solution: Run tests inside an `aco-launch` process

**How it works:**

1. Test cases are in files like `json_test_cases.py`
2. All tests in a file run sequentially in one `aco-launch` process
3. Individual test results are recorded
4. Results are sent back to pytest for reporting

This approach provides:

- Accurate testing of actual AST rewrites
- Per-test granularity in results
- Reduced overhead (one `aco-launch` per file, not per test)

## Writing New Tests

### Standard Test

```python
# tests/test_my_feature.py
import pytest

def test_my_feature():
    # Your test code
    assert result == expected
```

### Taint Propagation Test

For taint tests, add a test case file:

```python
# tests/taint/general_functions/my_test_cases.py
from aco.runner.taint_wrappers import TaintStr, get_taint_origins

def test_my_operation():
    tainted = TaintStr("hello", taint_origin=["origin1"])
    result = my_operation(tainted)

    # Verify taint propagated
    origins = get_taint_origins(result)
    assert "origin1" in origins
```

### API Patch Test

```python
# tests/test_api_patches.py
import pytest
from unittest.mock import MagicMock

def test_openai_patch():
    # Mock the OpenAI client
    mock_client = MagicMock()

    # Apply patches
    from aco.runner.monkey_patching.apply_monkey_patches import openai_patch
    openai_patch()

    # Test the patched behavior
    # ...
```

## Test Fixtures

Common fixtures are defined in `conftest.py`:

```python
@pytest.fixture
def tainted_string():
    return TaintStr("test", taint_origin=["test_origin"])

@pytest.fixture
def server_connection():
    # Setup server connection for integration tests
    pass
```

## Debugging Failed Tests

### View Server Logs

```bash
aco-server logs
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
- Taint tests require the full `aco-launch` environment

## Next Steps

- [Architecture](architecture.md) - Understand the system design
- [API patching](api-patching.md) - Write patches for new LLM APIs
