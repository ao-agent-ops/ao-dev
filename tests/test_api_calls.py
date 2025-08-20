"""
Integration test if the aco-launch command works as expected.
We insert cached responses into the database so we don't make actual
API calls. We register a UI, run an aco-launch command, and check if
the UI receives the correct number of graph_update messages.
"""

import json
import socket
import threading
import queue
import time
import pytest
from pathlib import Path
from agent_copilot.commands.server import launch_daemon_server
from agent_copilot.context_manager import set_parent_session_id
from get_api_objects import (
    create_anthropic_response,
    create_openai_input,
    create_openai_response,
    create_anthropic_input,
    create_vertexai_input,
    create_vertexai_response,
)
from workflow_edits.cache_manager import CACHE


def run_add_numbers_test(program_file, api_type, create_response_func, create_input_func):
    """
    Helper function to test add_numbers programs for different APIs.

    Args:
        program_file: Name of the user program file (e.g., "openai_add_numbers.py")
        api_type: API type for cache entries (e.g., "OpenAI.responses.create")
        create_response_func: Function to create mock API responses
        create_input_func: Function to create mock API inputs
    """
    print(f"Starting test for {program_file}...")

    # These are the exact input strings the monkey patches will see
    groundtruth_inputs = [
        "Output the number 42 and nothing else",
        "Add 1 to 42 and just output the result.",
        "Add 2 to 42 and just output the result.",
        "Add these two numbers together and just output the result: 43 + 44",
    ]

    cached_outputs = ["42", "43", "44", "87"]

    # 1. Connect as shim-control and get session_id
    print("1. Connecting as shim-control...")
    shim_sock = socket.create_connection(("127.0.0.1", 5959))
    shim_file = shim_sock.makefile("rw")

    test_dir = str(Path(__file__).parent)
    handshake = {
        "role": "shim-control",
        "cwd": test_dir,
        "command": f"aco-launch user_programs/{program_file}",
        "environment": {},
        "name": "test_api_calls",
    }
    shim_file.write(json.dumps(handshake) + "\n")
    shim_file.flush()

    response = json.loads(shim_file.readline().strip())
    session_id = response["session_id"]

    # 2. Deregister the shim-control to mark session as finished
    print("2. Deregistering shim-control...")
    deregister_msg = {"type": "deregister", "session_id": session_id}
    shim_file.write(json.dumps(deregister_msg) + "\n")
    shim_file.flush()
    shim_sock.close()

    # 3. Connect as UI and collect messages
    print("3. Connecting as UI...")
    ui_sock = socket.create_connection(("127.0.0.1", 5959))
    ui_file = ui_sock.makefile("rw")

    ui_handshake = {"role": "ui"}
    ui_file.write(json.dumps(ui_handshake) + "\n")
    ui_file.flush()

    message_queue = queue.Queue()

    def ui_listener():
        for line in ui_file:
            try:
                msg = json.loads(line.strip())
                message_queue.put(msg)
            except Exception:
                break

    ui_thread = threading.Thread(target=ui_listener, daemon=True)
    ui_thread.start()

    # 4. Populate database with cached responses
    print("4. Populating database with cached responses...")
    set_parent_session_id(session_id)
    for input_text, output_text in zip(groundtruth_inputs, cached_outputs):
        _, _, node_id = CACHE.get_in_out(create_input_func(input_text), api_type)
        response = create_response_func(output_text)
        CACHE.cache_output(node_id, response)

    # 5. Send restart message from UI connection
    print("5. Sending restart message...")
    restart_msg = {"type": "restart", "session_id": session_id}
    ui_file.write(json.dumps(restart_msg) + "\n")
    ui_file.flush()

    # 6. Collect graph_update messages
    print("6. Collecting graph_update messages...")
    graph_updates = 0
    timeout = 7
    start_time = time.time()

    # Run for 7 seconds, check how many graph_updates we get.
    # 7s should be enough given all responses are cached.
    while time.time() - start_time < timeout:
        try:
            msg = message_queue.get(timeout=1)
            # Filter for graph_update messages for our session
            if msg.get("type") == "graph_update" and msg.get("session_id") == session_id:
                graph_updates += 1
        except queue.Empty:
            continue
    ui_sock.close()

    # 7. Verify we got 5 graph updates (1 inital + 1 for each LLM call).
    print("7. Verifying results...")
    assert graph_updates == 5, f"Expected 5 graph_updates, got {graph_updates}"
    print(f"✅ Test passed for {program_file}! Got 5 graph_updates as expected")


@pytest.mark.parametrize(
    "program_file,api_type,create_response_func,create_input_func",
    [
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
        # ("vertexai_add_numbers.py", "vertexai_generate_content", create_vertexai_response, create_vertexai_input),
    ],
)
def test_add_numbers_api(program_file, api_type, create_response_func, create_input_func):
    """Test add_numbers programs for different APIs using cached responses."""
    launch_daemon_server()
    time.sleep(1)
    run_add_numbers_test(program_file, api_type, create_response_func, create_input_func)


if __name__ == "__main__":
    # Run individual tests for debugging
    print("Running OpenAI test...")
    run_add_numbers_test(
        "openai_add_numbers.py",
        "OpenAI.responses.create",
        create_openai_response,
        create_openai_input,
    )

    print("\nRunning Anthropic test...")
    run_add_numbers_test(
        "anthropic_add_numbers.py",
        "Anthropic.messages.create",
        create_anthropic_response,
        create_anthropic_input,
    )

    # NOTE: VertexAI needs an API key for client creation, so we skip it.
    # print("\nRunning VertexAI test...")
    # run_add_numbers_test("vertexai_add_numbers.py", "vertexai_generate_content", create_vertexai_response, create_vertexai_input)
