import asyncio
import threading
import os
import random
import json
import time
from aco.server.database_manager import DB
from aco.runner.develop_shim import DevelopShim
from aco.runner.develop_shim import ensure_server_running
from tests.utils import restart_server


async def main():
    # Restart server to ensure clean state for this test
    restart_server()
    
    shim = DevelopShim(
        script_path="./example_workflows/miroflow_deep_research/single_task.py",
        script_args=[],
        is_module_execution=False,
        project_root="./example_workflows/miroflow_deep_research",
        sample_id=None,
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
    assert return_code == 0, f"[DeepResearch] failed with return_code {return_code}"

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

    assert shim.restart_event.is_set(), "[DeepResearch] Restart even not set"
    shim.restart_event.clear()
    returncode_rerun = shim._run_user_script_subprocess()
    assert returncode_rerun == 0, f"[DeepResearch] re-run failed with return_code {return_code}"

    new_rows = DB.query_all(
        "SELECT node_id, input_overwrite, output FROM llm_calls WHERE session_id=?",
        (shim.session_id,),
    )

    new_graph_topology = DB.query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
        (shim.session_id,),
    )
    new_graph = json.loads(new_graph_topology["graph_topology"])

    assert len(rows) == len(
        new_rows
    ), "[DeepResearch] Length of LLM calls does not match after re-run"
    for old_row, new_row in zip(rows, new_rows):
        assert (
            old_row["node_id"] == new_row["node_id"]
        ), "[DeepResearch] Node IDs of LLM calls don't match after re-run. Potential cache issue."

    # Compare graph topology between runs
    assert len(graph["nodes"]) == len(
        new_graph["nodes"]
    ), "[DeepResearch] Number of nodes in graph topology doesn't match after re-run"
    assert len(graph["edges"]) == len(
        new_graph["edges"]
    ), "[DeepResearch] Number of edges in graph topology doesn't match after re-run"

    # Check that node IDs match between the two graphs
    original_node_ids = {node["id"] for node in graph["nodes"]}
    new_node_ids = {node["id"] for node in new_graph["nodes"]}
    assert (
        original_node_ids == new_node_ids
    ), "[DeepResearch] Node IDs in graph topology don't match after re-run"

    # Check that edge structure is identical
    original_edges = {(edge["source"], edge["target"]) for edge in graph["edges"]}
    new_edges = {(edge["source"], edge["target"]) for edge in new_graph["edges"]}
    assert (
        original_edges == new_edges
    ), "[DeepResearch] Edge structure in graph topology doesn't match after re-run"

    # Check that every node has at least one parent node, except "gpt-4.1" and first "o3"
    target_nodes = {edge["target"] for edge in graph["edges"]}
    first_o3_found = False

    for node in graph["nodes"]:
        node_id = node["id"]
        label = node.get("label", "")

        # Skip check for "gpt-4.1" nodes
        if label == "gpt-4.1":
            continue

        # Skip check for the first "o3" node only
        if label == "o3" and not first_o3_found:
            first_o3_found = True
            continue

        # All other nodes must have at least one parent
        assert (
            node_id in target_nodes
        ), f"[DeepResearch] Node {node_id} with label '{label}' has no parent nodes"

    # Cleanup: Close server connection and stop listener thread
    shim._kill_current_process()
    shim.send_deregister()
    shim.server_conn.close()
    shim.listener_thread.join(timeout=2)


def test_deepresearch():
    asyncio.run(main())


if __name__ == "__main__":
    test_deepresearch()
