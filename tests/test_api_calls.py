"""
Integration test if the develop command works as expected.
We insert cached responses into the database so we don't make actual
API calls. We register a UI, run a develop command, and check if the
UI receives the correct number of graph_update messages.
"""

import uuid
import json
import socket
import threading
import queue
import time
import pytest
from pathlib import Path
from workflow_edits import db


# Mock response structures for each API type
def create_anthropic_response(text):
    return json.dumps(
        {
            "id": "msg_01H3RB9Qa1QjhuHmDq6M23uE",
            "content": [{"citations": None, "text": text, "type": "text"}],
            "model": "claude-3-5-sonnet-20241022",
            "role": "assistant",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "type": "message",
            "usage": {
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "input_tokens": 24,
                "output_tokens": 5,
                "server_tool_use": None,
                "service_tier": "standard",
            },
        }
    )


def create_openai_response(text):
    # Mock OpenAI Responses API response structure based on the actual format
    return json.dumps(
        {
            "id": "resp_689755f5fe80819a9cc475181d1d09340d4c4a706fd6eec8",
            "created_at": 1754748406.0,
            "error": None,
            "incomplete_details": None,
            "instructions": None,
            "metadata": {},
            "model": "gpt-3.5-turbo",
            "object": "response",
            "output": [
                {
                    "id": "msg_689755f69c78819a8c285128e94055cd0d4c4a706fd6eec8",
                    "content": [
                        {"annotations": [], "text": text, "type": "output_text", "logprobs": []}
                    ],
                    "role": "assistant",
                    "status": "completed",
                    "type": "message",
                }
            ],
            "parallel_tool_calls": True,
            "temperature": 0.0,
            "tool_choice": "auto",
            "tools": [],
            "top_p": 1.0,
            "max_output_tokens": None,
            "previous_response_id": None,
            "reasoning": {"effort": None, "generate_summary": None, "summary": None},
            "service_tier": "default",
            "status": "completed",
            "text": {"format": {"type": "text"}, "verbosity": "medium"},
            "truncation": "disabled",
            "usage": {
                "input_tokens": 34,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 2,
                "output_tokens_details": {"reasoning_tokens": 0},
                "total_tokens": 36,
            },
            "user": None,
            "background": False,
            "max_tool_calls": None,
            "prompt_cache_key": None,
            "safety_identifier": None,
            "store": True,
            "top_logprobs": 0,
        }
    )


def create_vertexai_response(text):
    return json.dumps(
        {
            "sdk_http_response": "headers={'content-type': 'application/json; charset=UTF-8', 'vary': 'Origin, X-Origin, Referer', 'content-encoding': 'gzip', 'date': 'Sat, 09 Aug 2025 21:48:18 GMT', 'server': 'scaffolding on HTTPServer2', 'x-xss-protection': '0', 'x-frame-options': 'SAMEORIGIN', 'x-content-type-options': 'nosniff', 'server-timing': 'gfet4t7; dur=662', 'alt-svc': 'h3=\":443\"; ma=2592000,h3-29=\":443\"; ma=2592000', 'transfer-encoding': 'chunked'} body=None",
            "candidates": [
                f"content=Content(\n  parts=[\n    Part(\n      text='{text}'\n    ),\n  ],\n  role='model'\n) citation_metadata=None finish_message=None token_count=None finish_reason=<FinishReason.STOP: 'STOP'> url_context_metadata=None avg_logprobs=None grounding_metadata=None index=0 logprobs_result=None safety_ratings=None"
            ],
            "create_time": None,
            "model_version": "gemini-2.5-flash",
            "prompt_feedback": None,
            "response_id": "IsKXaOm3OoWW1MkPoMj8mAk",
            "usage_metadata": "cache_tokens_details=None cached_content_token_count=None candidates_token_count=2 candidates_tokens_details=None prompt_token_count=19 prompt_tokens_details=[ModalityTokenCount(\n  modality=<MediaModality.TEXT: 'TEXT'>,\n  token_count=19\n)] thoughts_token_count=77 tool_use_prompt_token_count=None tool_use_prompt_tokens_details=None total_token_count=98 traffic_type=None",
            "automatic_function_calling_history": [],
            "parsed": None,
        }
    )


def run_add_numbers_test(program_file, api_type, create_response_func):
    """
    Helper function to test add_numbers programs for different APIs.

    Args:
        program_file: Name of the user program file (e.g., "openai_add_numbers.py")
        api_type: API type for cache entries (e.g., "openai_v2_response")
        create_response_func: Function to create mock API responses
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

    # Close the fake shim connection
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
    for input_text, output_text in zip(groundtruth_inputs, cached_outputs):
        input_hash = db.hash_input(input_text)
        node_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO llm_calls (session_id, model, input, input_hash, node_id, output, api_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                "mock_model",
                input_text,
                input_hash,
                node_id,
                create_response_func(output_text),
                api_type,
            ),
        )

    # 5. Send restart message from UI connection
    print("5. Sending restart message...")
    restart_msg = {"type": "restart", "session_id": session_id}
    ui_file.write(json.dumps(restart_msg) + "\n")
    ui_file.flush()

    # 6. Collect graph_update messages
    print("6. Collecting graph_update messages...")
    graph_updates = []
    timeout = 7  # Run for 7 seconds, check how many graph_updates we get.
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            msg = message_queue.get(timeout=1)
            # Filter for graph_update messages for our session
            if msg.get("type") == "graph_update" and msg.get("session_id") == session_id:
                graph_updates.append(msg)
        except queue.Empty:
            continue
    ui_sock.close()

    # 7. Verify we got 5 graph updates (1 inital + 1 for each LLM call).
    print("7. Verifying results...")
    assert len(graph_updates) == 5, f"Expected 5 graph_updates, got {len(graph_updates)}"
    print(f"✅ Test passed for {program_file}! Got 5 graph_updates as expected")


@pytest.mark.parametrize(
    "program_file,api_type,create_response_func",
    [
        ("openai_add_numbers.py", "openai_v2_response", create_openai_response),
        ("anthropic_add_numbers.py", "anthropic_messages", create_anthropic_response),
        # ("vertexai_add_numbers.py", "vertexai_generate_content", create_vertexai_response),
    ],
)
def test_add_numbers_api(program_file, api_type, create_response_func):
    """Test add_numbers programs for different APIs using cached responses."""
    # TODO: Need to make sure server is running!
    run_add_numbers_test(program_file, api_type, create_response_func)


if __name__ == "__main__":
    # Run individual tests for debugging
    print("Running OpenAI test...")
    run_add_numbers_test("openai_add_numbers.py", "openai_v2_response", create_openai_response)

    print("\nRunning Anthropic test...")
    run_add_numbers_test(
        "anthropic_add_numbers.py", "anthropic_messages", create_anthropic_response
    )

    # NOTE: VertexAI needs an API key for client creation, so we skip it.
    # print("\nRunning VertexAI test...")
    # run_add_numbers_test("vertexai_add_numbers.py", "vertexai_generate_content", create_vertexai_response)
