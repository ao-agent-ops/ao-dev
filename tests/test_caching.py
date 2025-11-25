import asyncio
import threading
import os
import random
import json
import time
import pytest
from dataclasses import dataclass
from aco.server.database_manager import DB
from aco.runner.develop_shim import DevelopShim
from aco.runner.develop_shim import ensure_server_running

try:
    from tests.utils import restart_server
except ImportError:
    from utils import restart_server


@dataclass
class RunData:
    rows: list
    new_rows: list
    graph: list
    new_graph: list


async def run_test(script_path: str, project_root: str):
    # Restart server to ensure clean state for this test
    restart_server()

    shim = DevelopShim(
        script_path=script_path,
        script_args=[],
        is_module_execution=False,
        project_root=project_root,
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


def _caching_asserts(run_data_obj: RunData):
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


def _deepresearch_asserts(run_data_obj: RunData):
    # Check that every node has at least one parent node, except "gpt-4.1" and first "o3"
    target_nodes = {edge["target"] for edge in run_data_obj.graph["edges"]}
    first_o3_found = False

    for node in run_data_obj.graph["nodes"]:
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


def test_deepresearch():
    run_data_obj = asyncio.run(
        run_test(
            script_path="./example_workflows/miroflow_deep_research/single_task.py",
            project_root="./example_workflows/miroflow_deep_research",
        )
    )
    _caching_asserts(run_data_obj)
    _deepresearch_asserts(run_data_obj)


@pytest.mark.parametrize(
    "script_path",
    [
        "./example_workflows/debug_examples/anthropic_image_tool_call.py",
        "./example_workflows/debug_examples/anthropic_add_numbers.py",
        "./example_workflows/debug_examples/async_openai_add_numbers.py",
        "./example_workflows/debug_examples/mcp_simple_test.py",
        "./example_workflows/debug_examples/multiple_runs_asyncio.py",
        "./example_workflows/debug_examples/multiple_runs_sequential.py",
        "./example_workflows/debug_examples/multiple_runs_threading.py",
        "./example_workflows/debug_examples/openai_add_numbers.py",
        "./example_workflows/debug_examples/openai_chat.py",
        "./example_workflows/debug_examples/openai_chat_async.py",
        "./example_workflows/debug_examples/openai_tool_call.py",
        "./example_workflows/debug_examples/openai_async_agents.py",
        "./example_workflows/debug_examples/vertexai_add_numbers.py",
        "./example_workflows/debug_examples/vertexai_add_numbers_async.py",
        "./example_workflows/debug_examples/vertexai_gen_image.py",
        "./example_workflows/debug_examples/vertexai_streaming.py",
        "./example_workflows/debug_examples/vertexai_streaming_async.py",
    ],
)
def test_debug_examples(script_path: str):
    run_data_obj = asyncio.run(
        run_test(script_path=script_path, project_root="./example_workflows/debug_examples")
    )
    _caching_asserts(run_data_obj)


if __name__ == "__main__":
    # test_deepresearch()
    test_debug_examples("./example_workflows/debug_examples/anthropic_add_numbers.py")
