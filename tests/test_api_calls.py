"""
Integration test: run aco-launch command and verify graph updates.
"""

import json
import socket
import threading
import queue
import time
import pytest
import os
import sys
from pathlib import Path

from aco.server.database_manager import DB

# Add parent directory to path so we can import from tests module
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

from aco.cli.aco_server import launch_daemon_server
from aco.runner.context_manager import set_parent_session_id
from aco.common.constants import ACO_LOG_PATH, REMOTE_DATABASE_URL
from aco.server.cache_manager import CACHE
from tests.get_api_objects import (
    create_anthropic_response,
    create_openai_input,
    create_openai_response,
    create_anthropic_input,
)


def print_server_logs():
    """Print recent server logs for debugging."""
    log_file = ACO_LOG_PATH
    print(f"Looking for server logs at: {log_file}")
    if os.path.exists(log_file):
        try:
            with open(log_file, "r") as f:
                lines = f.readlines()
                print(f"=== Recent Server Logs ({len(lines)} total lines) ===")
                # Print more lines for better debugging
                for line in lines[-20:]:  # Last 20 lines
                    print(f"LOG: {line.strip()}")
                print("=" * 50)
        except Exception as e:
            print(f"Error reading logs: {e}")
    else:
        print(f"No server log file found at {log_file}")
        # Check if the directory exists
        log_dir = os.path.dirname(log_file)
        if os.path.exists(log_dir):
            print(f"Log directory exists, files: {os.listdir(log_dir)}")
        else:
            print(f"Log directory does not exist: {log_dir}")


def wait_for_server():
    """Wait for server to be ready."""
    print("Waiting for server on 127.0.0.1:5959...")
    for i in range(5):
        try:
            print(f"  Attempt {i+1}/5...")
            socket.create_connection(("127.0.0.1", 5959), timeout=2).close()
            print("  Server is responding!")
            return True
        except Exception as e:
            print(f"  Connection failed: {e}")
            time.sleep(1)
    print("  Server failed to respond after 5 attempts")
    return False


def run_test(program_file, api_type, create_response_func, create_input_func, http_calls, db_backend="local"):
    """Run the actual test logic."""
    print(f"\n=== Starting test for {program_file} with {api_type} ===")
    print(f"Database backend: {db_backend}")

    # Test inputs and expected outputs
    inputs = [
        "Output the number 42 and nothing else",
        "Add 1 to 42 and just output the result.",
        "Add 2 to 42 and just output the result.",
        "Add these two numbers together and just output the result: 43 + 44",
    ]
    outputs = ["42", "43", "44", "87"]

    initial_http_calls = len(http_calls.calls) if http_calls else 0
    print(f"Initial HTTP calls: {initial_http_calls}")

    # HACK: Inserts takes longer for remote, give additional 5s
    TEST_TIMEOUT = 8
    if db_backend != "local":
        TEST_TIMEOUT += 5

    # 1. Set DB backend.
    print(f"Switching server database backend to: {db_backend}")
    admin_sock = socket.create_connection(("127.0.0.1", 5959))
    admin_file = admin_sock.makefile("rw")
    
    admin_handshake = {"type": "hello", "role": "admin", "script": "test_admin"}
    admin_file.write(json.dumps(admin_handshake) + "\n")
    admin_file.flush()
    
    db_mode_msg = {"type": "set_database_mode", "mode": db_backend}
    admin_file.write(json.dumps(db_mode_msg) + "\n")
    DB.switch_mode(db_backend)
    admin_file.flush()
    admin_sock.close()
    print(f"Switched server database to {db_backend} mode")

    # 2. Connect as shim-control to register session
    print("Connecting to shim-control...")
    shim_sock = socket.create_connection(("127.0.0.1", 5959))
    shim_file = shim_sock.makefile("rw")

    # Use --project-root to override the project root for this test
    test_project_root = str(Path(__file__).parent)  # /path/to/tests/
    handshake = {
        "role": "shim-control",
        "cwd": test_project_root,
        "command": f"aco-launch --project-root {test_project_root} user_programs/{program_file}",
        "environment": {},
        "name": "test_api_calls",
    }
    print(f"Sending handshake: {handshake}")
    shim_file.write(json.dumps(handshake) + "\n")
    shim_file.flush()

    response = json.loads(shim_file.readline().strip())
    session_id = response["session_id"]
    print(f"Got session_id: {session_id}")

    # 3. Deregister to mark session as finished
    deregister_msg = {"type": "deregister", "session_id": session_id}
    shim_file.write(json.dumps(deregister_msg) + "\n")
    shim_file.flush()
    shim_sock.close()

    # 4. Connect as UI to receive messages
    ui_sock = socket.create_connection(("127.0.0.1", 5959))
    ui_file = ui_sock.makefile("rw")

    ui_file.write(json.dumps({"role": "ui"}) + "\n")
    ui_file.flush()

    message_queue = queue.Queue()

    def ui_listener():
        for line in ui_file:
            try:
                msg = json.loads(line.strip())
                message_queue.put(msg)
            except:
                break

    threading.Thread(target=ui_listener, daemon=True).start()

    # 5. Cache responses in database
    print(f"Setting parent session ID to: {session_id}")
    set_parent_session_id(session_id)
    print(f"Caching {len(inputs)} responses...")
    for i, (input_text, output_text) in enumerate(zip(inputs, outputs)):
        print(f"  Caching response {i+1}: '{input_text}' -> '{output_text}'")
        _, _, node_id = CACHE.get_in_out(create_input_func(input_text), api_type)
        response = create_response_func(output_text)
        CACHE.cache_output(node_id, response)
        print(f"  Cached with node_id: {node_id}")

    # 6. Send restart to trigger execution
    restart_msg = {"type": "restart", "session_id": session_id}
    print(f"Sending restart message: {restart_msg}")
    ui_file.write(json.dumps(restart_msg) + "\n")
    ui_file.flush()

    # 7. Collect graph updates
    graph_updates = 0
    start_time = time.time()
    print("Waiting for graph updates...")

    while time.time() - start_time < TEST_TIMEOUT: # Messages need to arrive within this time
        try:
            msg = message_queue.get(timeout=1)
            if msg.get("type") == "graph_update" and msg.get("session_id") == session_id:
                graph_updates += 1
                print(f"Graph update #{graph_updates} received")
        except queue.Empty:
            elapsed = time.time() - start_time
            print(f"No message received, elapsed: {elapsed:.1f}s")
            continue

    ui_sock.close()

    # 8. Verify results
    final_http_calls = len(http_calls.calls) if http_calls else 0
    http_calls_made = final_http_calls - initial_http_calls

    print(f"\n=== Final Results ===")
    print(f"Graph updates: {graph_updates}, HTTP calls: {http_calls_made}")
    print(f"Expected: 5 graph updates, 0 HTTP calls")

    if graph_updates != 5:
        print(f"ERROR: Expected 5 graph updates, got {graph_updates}")
        print_server_logs()

    if http_calls_made != 0:
        print(f"ERROR: Expected 0 HTTP calls, got {http_calls_made}")
        if http_calls:
            print("HTTP calls made:")
            for call in http_calls.calls:
                print(f"  {call.request.method} {call.request.url}")

    assert graph_updates == 5, f"Expected 5 graph updates, got {graph_updates}"
    assert http_calls_made == 0, f"Expected 0 HTTP calls, got {http_calls_made}"


@pytest.mark.parametrize(
    "program_file,api_type,create_response_func,create_input_func,db_backend",
    [
        (
            "openai_add_numbers.py",
            "OpenAI.responses.create",
            create_openai_response,
            create_openai_input,
            "local",
        ),
        (
            "openai_add_numbers.py",
            "OpenAI.responses.create",
            create_openai_response,
            create_openai_input,
            "remote",
        ),
        (
            "anthropic_add_numbers.py",
            "Anthropic.messages.create",
            create_anthropic_response,
            create_anthropic_input,
            "local",
        ),
        (
            "anthropic_add_numbers.py",
            "Anthropic.messages.create",
            create_anthropic_response,
            create_anthropic_input,
            "remote",
        ),
    ],
)
def test_api_calls(program_file, api_type, create_response_func, create_input_func, db_backend, http_calls):
    """Test API calls with cached responses."""
    print(f"\n=== Starting test_api_calls for {program_file} ===")
    print(f"API type: {api_type}")

    # Print environment info for CI debugging
    print(f"Environment info:")
    print(f"  Current working directory: {os.getcwd()}")
    print(f"  Python path: {sys.executable}")
    print(f"  ACO_LOG_PATH: {ACO_LOG_PATH}")
    print(f"  HOME: {os.environ.get('HOME', 'Not set')}")
    print(f"  User: {os.environ.get('USER', 'Not set')}")
    print(f"  CI: {os.environ.get('CI', 'Not set')}")
    print(f"  GITHUB_ACTIONS: {os.environ.get('GITHUB_ACTIONS', 'Not set')}")

    # Check OpenAI version and environment
    try:
        import openai

        print(f"OpenAI version: {openai.__version__}")
    except Exception as e:
        print(f"Failed to import openai: {e}")

    print(f"OPENAI_API_KEY set: {'OPENAI_API_KEY' in os.environ}")
    print(f"ANTHROPIC_API_KEY set: {'ANTHROPIC_API_KEY' in os.environ}")
    print(f"GOOGLE_API_KEY set: {'GOOGLE_API_KEY' in os.environ}")

    # Start server
    print("Starting daemon server...")
    launch_daemon_server()
    print("Waiting 3 seconds for server to start...")
    time.sleep(3)

    print("Checking if server is ready...")
    if not wait_for_server():
        print("Server is not responding!")
        print_server_logs()
        pytest.fail("Server not responding")
    else:
        print("Server is ready!")

    try:
        run_test(program_file, api_type, create_response_func, create_input_func, http_calls, db_backend)
        print(f"=== Test {program_file} completed successfully ===")
    except Exception as e:
        print(f"=== Test {program_file} failed with exception: {e} ===")
        print_server_logs()
        raise


if __name__ == "__main__":
    """
    Allow running tests manually: python test_api_calls.py [openai|anthropic] [local|remote]

    Examples:
        python test_api_calls.py openai local
        python test_api_calls.py anthropic remote
        python test_api_calls.py openai  # defaults to local
        python test_api_calls.py  # runs both APIs with both backends
    """
    import sys

    class DummyHTTPCalls:
        """Mock http_calls fixture for manual testing."""

        def __init__(self):
            self.calls = []

    # Determine which tests to run
    base_test_cases = [
        (
            "openai_add_numbers.py",
            "OpenAI.responses.create",
            create_openai_response,
            create_openai_input,
        ),
        (
            "anthropic_add_numbers.py",
            "Anthropic.messages.create",
            create_anthropic_response,
            create_anthropic_input,
        ),
    ]

    # Generate test cases with both backends
    test_cases = []
    for program_file, api_type, create_response_func, create_input_func in base_test_cases:
        test_cases.extend([
            (program_file, api_type, create_response_func, create_input_func, "local"),
            (program_file, api_type, create_response_func, create_input_func, "remote"),
        ])

    # Parse command line arguments
    if len(sys.argv) > 1:
        api_filter = sys.argv[1].lower()
        db_filter = sys.argv[2].lower() if len(sys.argv) > 2 else None
        
        if api_filter in ["openai", "anthropic"]:
            # Filter by API type
            filtered_cases = []
            for case in test_cases:
                if api_filter in case[0].lower():
                    filtered_cases.append(case)
            test_cases = filtered_cases
        elif api_filter not in ["openai", "anthropic", "both"]:
            print(f"Unknown API argument: {api_filter}")
            print("Usage: python test_api_calls.py [openai|anthropic|both] [local|remote]")
            sys.exit(1)
        
        if db_filter in ["local", "remote"]:
            # Filter by database backend
            filtered_cases = []
            for case in test_cases:
                if case[4] == db_filter:
                    filtered_cases.append(case)
            test_cases = filtered_cases
        elif db_filter is not None:
            print(f"Unknown database backend: {db_filter}")
            print("Usage: python test_api_calls.py [openai|anthropic|both] [local|remote]")
            sys.exit(1)

    # Run selected tests
    http_calls = DummyHTTPCalls()
    failed_tests = []

    for program_file, api_type, create_response_func, create_input_func, db_backend in test_cases:
        test_name = f"{program_file}({db_backend})"
        try:
            test_api_calls(
                program_file, api_type, create_response_func, create_input_func, db_backend, http_calls
            )
            print(f"\n✓ Test passed: {test_name}\n")
        except AssertionError as e:
            print(f"\n✗ Test failed: {test_name}")
            print(f"  Error: {e}\n")
            failed_tests.append(test_name)
        except Exception as e:
            print(f"\n✗ Test error: {test_name}")
            print(f"  Error: {e}\n")
            failed_tests.append(test_name)

    # Summary
    passed = len(test_cases) - len(failed_tests)
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{len(test_cases)} tests passed")
    if failed_tests:
        print(f"Failed tests: {', '.join(failed_tests)}")
        sys.exit(1)
    print(f"{'='*50}")
