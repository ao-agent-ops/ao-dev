import threading
import os
import random
import json
import time
import subprocess
from dataclasses import dataclass
from aco.server.database_manager import DB
from aco.runner.develop_shim import DevelopShim
from aco.runner.develop_shim import ensure_server_running


@dataclass
class RunData:
    rows: list
    new_rows: list
    graph: list
    new_graph: list


def restart_server():
    """Restart the server to ensure clean state for tests."""
    subprocess.run(["aco-server", "restart"], check=False)
    time.sleep(1)


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
        "SELECT node_id, input_overwrite, output FROM llm_calls WHERE session_id=?",
        (shim.session_id,),
    )

    graph_topology = DB.query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
        (shim.session_id,),
    )
    graph = json.loads(graph_topology["graph_topology"])

    # send a restart message
    message = {"type": "restart", "role": "shim-control", "session_id": shim.session_id}
    shim.server_conn.sendall((json.dumps(message) + "\n").encode("utf-8"))

    time.sleep(2)

    assert shim.restart_event.is_set(), "Restart even not set"
    shim.restart_event.clear()
    returncode_rerun = shim._run_user_script_subprocess()
    assert returncode_rerun == 0, f"re-run failed with return_code {return_code}"

    new_rows = DB.query_all(
        "SELECT node_id, input_overwrite, output FROM llm_calls WHERE session_id=?",
        (shim.session_id,),
    )

    new_graph_topology = DB.query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
        (shim.session_id,),
    )
    new_graph = json.loads(new_graph_topology["graph_topology"])

    # Cleanup: Close server connection and stop listener thread
    shim._kill_current_process()
    shim.send_deregister()
    shim.server_conn.close()
    shim.listener_thread.join(timeout=2)

    run_data_obj = RunData(rows=rows, new_rows=new_rows, graph=graph, new_graph=new_graph)

    return run_data_obj


def caching_asserts(run_data_obj: RunData):
    assert len(run_data_obj.rows) == len(
        run_data_obj.new_rows
    ), "Length of LLM calls does not match after re-run"
    for old_row, new_row in zip(run_data_obj.rows, run_data_obj.new_rows):
        assert (
            old_row["node_id"] == new_row["node_id"]
        ), "Node IDs of LLM calls don't match after re-run. Potential cache issue."

    # Compare graph topology between runs
    assert len(run_data_obj.graph["nodes"]) == len(
        run_data_obj.new_graph["nodes"]
    ), "Number of nodes in graph topology doesn't match after re-run"
    assert len(run_data_obj.graph["edges"]) == len(
        run_data_obj.new_graph["edges"]
    ), "Number of edges in graph topology doesn't match after re-run"

    # Check that node IDs match between the two graphs
    original_node_ids = {node["id"] for node in run_data_obj.graph["nodes"]}
    new_node_ids = {node["id"] for node in run_data_obj.new_graph["nodes"]}
    assert original_node_ids == new_node_ids, "Node IDs in graph topology don't match after re-run"

    # Check that edge structure is identical
    original_edges = {(edge["source"], edge["target"]) for edge in run_data_obj.graph["edges"]}
    new_edges = {(edge["source"], edge["target"]) for edge in run_data_obj.new_graph["edges"]}
    assert (
        original_edges == new_edges
    ), "Edge structure in graph topology doesn't match after re-run"
