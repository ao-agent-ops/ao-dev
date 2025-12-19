import asyncio
import threading
import os
import random
import json
import time
import pytest
from flatten_json import flatten, unflatten_list
from dataclasses import dataclass
from aco.server.database_manager import DB
from aco.runner.develop_shim import DevelopShim
from aco.runner.develop_shim import ensure_server_running

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


async def run_test(script_path: str, project_root: str):
    # Restart server to ensure clean state for this test
    restart_server()

    shim = DevelopShim(
        script_path=script_path,
        script_args=[],
        is_module_execution=False,
        project_root=project_root,
        run_name=None,
    )
    aco_random_seed = random.randint(0, 2**31 - 1)
    os.environ["ACO_SEED"] = str(aco_random_seed)

    ensure_server_running()
    shim._connect_to_server()

    # Explicitly set both server and client to use local SQLite database
    # Send message to server to switch to local mode
    DB.switch_mode("local")
    set_db_mode_msg = {"type": "set_database_mode", "mode": "local"}
    shim.server_conn.sendall((json.dumps(set_db_mode_msg) + "\n").encode("utf-8"))

    # Give the server a moment to complete database mode switch and transaction
    time.sleep(0.2)

    # Start background thread to listen for server messages
    shim.listener_thread = threading.Thread(
        target=shim._listen_for_server_messages, args=(shim.server_conn,)
    )
    shim.listener_thread.start()

    return_code = shim._run_user_script_subprocess()
    assert return_code == 0, f"failed with return_code {return_code}"

    print("~~~~ session_id", shim.session_id)

    rows = DB.query_all(
        "SELECT node_id, input, input_overwrite, output, session_id FROM llm_calls WHERE session_id=?",
        (shim.session_id,),
    )

    # send edit input message
    message = find_row_and_get_edit_msg(script_path, rows)
    shim.server_conn.sendall((json.dumps(message) + "\n").encode("utf-8"))

    # send a restart message
    message = {"type": "restart", "role": "shim-control", "session_id": shim.session_id}
    shim.server_conn.sendall((json.dumps(message) + "\n").encode("utf-8"))

    time.sleep(2)

    assert shim.restart_event.is_set(), "Restart even not set"
    shim.restart_event.clear()
    returncode_rerun = shim._run_user_script_subprocess()
    assert returncode_rerun == 0, f"re-run failed with return_code {return_code}"

    graph_topology = DB.query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
        (shim.session_id,),
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

    # Re-run again without editing
    message = {"type": "restart", "role": "shim-control", "session_id": shim.session_id}
    shim.server_conn.sendall((json.dumps(message) + "\n").encode("utf-8"))

    time.sleep(2)

    assert shim.restart_event.is_set(), "Restart even not set"
    shim.restart_event.clear()
    returncode_rerun = shim._run_user_script_subprocess()
    assert returncode_rerun == 0, f"re-run failed with return_code {return_code}"

    new_graph_topology = DB.query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
        (shim.session_id,),
    )
    new_graph = json.loads(new_graph_topology["graph_topology"])

    assert len(graph["nodes"]) == len(
        new_graph["nodes"]
    ), f"Graph after re-run with edit does not have same number of nodes as before. Graph before has {len(graph['nodes'])} nodes and graph after has {graph['nodes']} nodes."

    for node1, node2 in zip(graph["nodes"], new_graph["nodes"]):
        assert node1["id"] == node2["id"], "Node IDs don't match."

    # Cleanup: Close server connection and stop listener thread
    shim._kill_current_process()
    shim.send_deregister()
    shim.server_conn.close()
    shim.listener_thread.join(timeout=2)


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
