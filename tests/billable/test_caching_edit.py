import asyncio
import os
import random
import json
import time
import socket
import subprocess
import sys
import re
import pytest
from flatten_json import flatten, unflatten_list
from dataclasses import dataclass
from aco.server.database_manager import DB
from aco.common.constants import HOST, PORT

try:
    from tests.billable.caching_utils import restart_server
except ImportError:
    from caching_utils import restart_server


@dataclass
class RunData:
    rows: list
    new_rows: list
    graph: list
    new_graph: list


def get_key_value_new_value(script_path: str):
    if "together_add_numbers" in script_path:
        key_to_edit = "to_show.messages.0.content"
        value_to_edit = "Add 2 to 42 and just output the result."
        new_value = "Add 2 to 43 and just output the result."
    elif "anthropic_add_numbers" in script_path:
        key_to_edit = "to_show.messages.0.content"
        value_to_edit = "Add 2 to 42 and just output the result."
        new_value = "Add 2 to 43 and just output the result."
    elif "vertexai_add_numbers" in script_path:
        key_to_edit = "to_show.contents.0.parts.0.text"
        value_to_edit = "Add 2 to 42 and just output the result."
        new_value = "Add 2 to 43 and just output the result."
    else:
        raise NotImplementedError
    return key_to_edit, value_to_edit, new_value


def get_target_output_key_and_value(script_path: str):
    if "together_add_numbers" in script_path:
        target_key = "raw.content.choices.0.message.content"
        target_value_after_edit = "88"
    elif "anthropic_add_numbers" in script_path:
        target_key = "raw.content.content.0.text"
        target_value_after_edit = "88"
    elif "vertexai_add_numbers" in script_path:
        target_key = "raw.content.candidates.0.content.parts.0.text"
        target_value_after_edit = "88"
    else:
        raise NotImplementedError
    return target_key, target_value_after_edit


def find_row_and_get_edit_msg(script_path: str, rows: list):
    key_to_edit, value_to_edit, new_value = get_key_value_new_value(script_path)

    node_id = None
    session_id = None
    for row in rows:
        input_dict = json.loads(json.loads(row["input"])["input"])
        flattened_input_dict = flatten(input_dict, ".")
        if key_to_edit in flattened_input_dict and value_to_edit in flattened_input_dict.values():
            # we found the row to edit
            flattened_input_dict[key_to_edit] = new_value
            node_id = row["node_id"]
            session_id = row["session_id"]
            break
    assert node_id, "Did not find node in DB rows that matched pattern"
    edited_input_dict = unflatten_list(flattened_input_dict, ".")
    msg = {
        "type": "edit_input",
        "role": "ui",
        "session_id": session_id,
        "node_id": node_id,
        "attachments": [],
        "value": json.dumps(edited_input_dict),
    }
    return msg


def _run_script_with_aco_launch(script_path: str, project_root: str, env: dict) -> tuple[int, str]:
    """
    Run a script using aco-launch and return (return_code, session_id).

    Parses the session_id from the runner's output.
    """
    env["ACO_NO_DEBUG_MODE"] = "True"
    proc = subprocess.Popen(
        [sys.executable, "-m", "aco.cli.aco_launch", "--project-root", project_root, script_path],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    output_lines = []
    session_id = None

    # Read output and look for session_id
    for line in proc.stdout:
        print(line, end="")  # Print to terminal in real-time
        output_lines.append(line)
        # Look for session_id in log output
        if "session_id:" in line or "Registered with session_id:" in line:
            # Extract session_id from line like "Registered with session_id: abc123"
            match = re.search(r"session_id[:\s]+([a-f0-9-]+)", line, re.IGNORECASE)
            if match:
                session_id = match.group(1)

    proc.wait()
    return proc.returncode, session_id


def send_message_to_server(msg: dict) -> None:
    """Send a message to the develop server via a new socket connection."""
    conn = socket.create_connection((HOST, PORT), timeout=10)
    try:
        # Send a hello message to identify as a UI client
        hello = {"type": "hello", "role": "ui"}
        conn.sendall((json.dumps(hello) + "\n").encode("utf-8"))

        # Read the hello response (session_id assignment for UI)
        file_obj = conn.makefile(mode="r")
        file_obj.readline()  # discard response

        # Send the actual message
        conn.sendall((json.dumps(msg) + "\n").encode("utf-8"))

        # Give server time to process
        time.sleep(0.5)
    finally:
        conn.close()


async def run_test(script_path: str, project_root: str):
    # Restart server to ensure clean state for this test
    restart_server()

    # Set up environment
    env = os.environ.copy()
    aco_random_seed = random.randint(0, 2**31 - 1)
    env["ACO_SEED"] = str(aco_random_seed)

    # Ensure we use local SQLite database
    DB.switch_mode("local")

    # First run
    return_code, session_id = _run_script_with_aco_launch(script_path, project_root, env)
    assert return_code == 0, f"First run failed with return_code {return_code}"
    assert session_id is not None, "Could not extract session_id from first run output"

    print(f"~~~~ session_id {session_id}")

    rows = DB.query_all(
        "SELECT node_id, input, input_overwrite, output, session_id FROM llm_calls WHERE session_id=?",
        (session_id,),
    )

    # Send edit input message to server
    edit_message = find_row_and_get_edit_msg(script_path, rows)
    send_message_to_server(edit_message)

    # Wait for server to process edit
    time.sleep(1)

    # Send restart message to clear the graph before rerun
    # This is needed so the server clears the old graph and accepts new nodes with updated outputs
    restart_message = {"type": "restart", "role": "ui", "session_id": session_id}
    send_message_to_server(restart_message)
    time.sleep(1)

    # Second run (rerun with edit applied)
    # Pass the same session_id so it reuses the cache but applies the edit
    env["AGENT_COPILOT_SESSION_ID"] = session_id
    returncode_rerun, _ = _run_script_with_aco_launch(script_path, project_root, env)
    assert returncode_rerun == 0, f"Re-run failed with return_code {returncode_rerun}"

    graph_topology = DB.query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
        (session_id,),
    )
    graph = json.loads(graph_topology["graph_topology"])

    target_key, target_value_after_edit = get_target_output_key_and_value(script_path)
    for node in graph["nodes"]:
        targets_of_node = set([e["target"] for e in graph["edges"] if e["source"] == node["id"]])
        if len(targets_of_node) == 0:
            break

    output_dict = json.loads(node["output"])
    output_dict_flattened = flatten(output_dict, ".")
    assert (
        target_value_after_edit == output_dict_flattened[target_key]
    ), f"{script_path}: output after edit expected to be {target_value_after_edit} but is {output_dict_flattened[target_key]}"

    # Send restart message to clear the graph before third run
    restart_message = {"type": "restart", "role": "ui", "session_id": session_id}
    send_message_to_server(restart_message)
    time.sleep(1)

    # Third run without editing (should use cached results including the edit)
    returncode_third, _ = _run_script_with_aco_launch(script_path, project_root, env)
    assert returncode_third == 0, f"Third run failed with return_code {returncode_third}"

    new_graph_topology = DB.query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
        (session_id,),
    )
    new_graph = json.loads(new_graph_topology["graph_topology"])

    assert len(graph["nodes"]) == len(
        new_graph["nodes"]
    ), f"Graph after re-run with edit does not have same number of nodes as before. Graph before has {len(graph['nodes'])} nodes and graph after has {len(new_graph['nodes'])} nodes."

    for node1, node2 in zip(graph["nodes"], new_graph["nodes"]):
        assert node1["id"] == node2["id"], "Node IDs don't match."


@pytest.mark.parametrize(
    "script_path",
    [
        "./example_workflows/debug_examples/together_add_numbers.py",
        "./example_workflows/debug_examples/anthropic_add_numbers.py",
        "./example_workflows/debug_examples/vertexai_add_numbers.py",
        "./example_workflows/debug_examples/vertexai_add_numbers_async.py",
    ],
)
def test_debug_examples(script_path: str):
    asyncio.run(run_test(script_path=script_path, project_root="."))


if __name__ == "__main__":
    test_debug_examples("./example_workflows/debug_examples/anthropic_add_numbers.py")
