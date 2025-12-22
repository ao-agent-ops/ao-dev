# Tests

## Test Organization

- **`tests/local/`** - Tests that don't use billable, third-party API calls
- **`tests/billable/`** - Tests that use third-party APIs (OpenAI, Anthropic, etc.)

## CI/CD Integration

### Local Tests (Automatic)
- **Workflow**: `.github/workflows/test-local.yml`
- **Trigger**: Every push to any branch
- **Command**: `pytest -v -s tests/local/`
- **Cost**: Free - no external API calls

### Billable Tests (Manual Approval Required)
- **Workflow**: `.github/workflows/test-billable.yml`
- **Trigger**: 
  - Manual trigger via GitHub Actions UI (`workflow_dispatch`)
  - Automatically on PRs to main branch (but requires approval)
- **Command**: `pytest -v -s tests/billable/`
- **Cost**: Uses external LLM APIs
- **Access**: Requires admin approval through GitHub Environment protection

#### How to Run Billable Tests

1. **From a Pull Request** (Recommended):
   - When you open a PR to main, billable tests automatically queue but wait for approval
   - In the PR's "Checks" section, you'll see "Test Billable (Requires Approval) - Waiting for approval"
   - Admins will see a **"Review deployments"** button directly in the PR
   - Click the button → Approve → Tests run immediately
   - Results appear in the PR checks

2. **Manual Trigger** (for testing outside of PRs):
   - Go to Actions tab → "Test Billable (Requires Approval)" workflow
   - Click "Run workflow" → Enter reason → Run
   - Admins can run immediately; others need approval

### GitHub Environment Configuration

The repository has a `billable-tests` environment configured with:
- **Required reviewers**: Repository admins
- **Prevent self-review**: Enabled (triggerer cannot approve their own run)
- **Branch restrictions**: Only main and protected branches

This ensures billable tests can only be run with explicit admin approval.

### test_api_calls.py

For `test_api_calls.py`, the user progam is executed as a replay by the server. So you need to run `ao-server logs` to see the output of the user program (e.g., how it crashed).

### test_taint.py (`taint/general_functions` test cases)

This test has a more involved set up because it relies on the develop_server rewriting ASTs and storing the compiled .pyc files. The problem is that pytest ignores .pyc files and always compiles from the (unmodified) source.

So we have files with test cases in `taint/general_functions` and run them inside an `ao-record` process, the same way that the user would run the test program in practice. However, `ao-record` has overheads which makes running 100s of tests slow. To overcome this, we run all tests in a file (e.g., `json_test_cases.py`) inside the same `ao-record` process as if they were one program sequentially executing each test. For all tests, we individually record if they failed and the Traceback of failing tests. We then send this information back to pytest, which launched the `ao-record` process and logs test failures on a per-test granularity.