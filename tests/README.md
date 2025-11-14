# Tests

Some notes on more involved tests.

### test_api_calls.py

For `test_api_calls.py`, the user progam is executed as a replay by the server. So you need to run `aco-server logs` to see the output of the user program (e.g., how it crashed).

### test_taint.py (`taint/general_functions` test cases)

This test has a more involved set up because it relies on the develop_server rewriting ASTs and storing the compiled .pyc files. The problem is that pytest ignores .pyc files and always compiles from the (unmodified) source.

So we have files with test cases in `taint/general_functions` and run them inside an `aco-launch` process, the same way that the user would run the test program in practice. However, `aco-launch` has overheads which makes running 100s of tests slow. To overcome this, we run all tests in a file (e.g., `json_test_cases.py`) inside the same `aco-launch` process as if they were one program sequentially executing each test. For all tests, we individually record if they failed and the Traceback of failing tests. We then send this information back to pytest, which launched the `aco-launch` process and logs test failures on a per-test granularity.