import asyncio
import threading
import os
import random
import json
import time
from aco.server.database_manager import DB
from aco.runner.develop_shim import DevelopShim
from aco.runner.develop_shim import ensure_server_running


async def main():
    print("\n" + "="*80)
    print("DEBUG: Starting test_deep_research main()")
    print("="*80)
    
    # Ensure we're using local SQLite for this test
    DB.switch_mode("local")
    
    # Check database file exists
    import os as os_debug
    db_path = os_debug.path.expanduser("~/.cache/agent-copilot/db/experiments.sqlite")
    
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
    
    # Debug: Check if session_id was set after connection
    print(f"DEBUG: After _connect_to_server, shim.session_id = {shim.session_id}")
    assert shim.session_id is not None, "session_id was not set after connecting to server"
    
    # Check if experiment was created in database immediately after connection
    print("DEBUG: Checking if experiment exists in database immediately after connection...")
    immediate_check = DB.query_one(
        "SELECT session_id, name FROM experiments WHERE session_id=?",
        (shim.session_id,),
    )
    print(f"DEBUG: Immediate experiment check result: {immediate_check}")
    
    # Also check all experiments
    # all_experiments = DB.query_all("SELECT session_id, name FROM experiments", ())
    # print(f"DEBUG: All experiments in database: {[exp['session_id'] for exp in all_experiments] if all_experiments else 'NONE'}")

    # Start background thread to listen for server messages
    shim.listener_thread = threading.Thread(
        target=shim._listen_for_server_messages, args=(shim.server_conn,)
    )
    shim.listener_thread.start()

    try:
        # print("DEBUG: Setting up subprocess environment...")
        # env = shim._setup_monkey_patching_env()
        # print(f"DEBUG: AGENT_COPILOT_SESSION_ID in env: {'AGENT_COPILOT_SESSION_ID' in env}")
        # if 'AGENT_COPILOT_SESSION_ID' in env:
        #     print(f"DEBUG: AGENT_COPILOT_SESSION_ID value: {env['AGENT_COPILOT_SESSION_ID']}")
        # print(f"DEBUG: AGENT_COPILOT_ENABLE_TRACING in env: {env.get('AGENT_COPILOT_ENABLE_TRACING', 'NOT SET')}")
        
        # print("DEBUG: Running user script subprocess...")
        return_code = shim._run_user_script_subprocess()
        print(f"DEBUG: Subprocess returned with code: {return_code}")
        assert return_code == 0, f"[DeepResearch] failed with return_code {return_code}"

        # Check database after subprocess
        # print("DEBUG: Checking database after subprocess execution...")
        # all_experiments_after = DB.query_all("SELECT session_id, name FROM experiments", ())
        # print(f"DEBUG: All experiments after subprocess: {[exp['session_id'] for exp in all_experiments_after] if all_experiments_after else 'NONE'}")
        
        rows = DB.query_all(
            "SELECT node_id, input_overwrite, output FROM llm_calls WHERE session_id=?",
            (shim.session_id,),
        )
        print(f"DEBUG: LLM calls found: {len(rows) if rows else 0}")

        print("DEBUG: Querying experiment record...")
        graph_topology = DB.query_one(
            "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
            (shim.session_id,),
        )
        print(f"DEBUG: Graph topology query result: {graph_topology}")
        
        if graph_topology is None:
            print("DEBUG: CRITICAL - No experiment found! Let's debug further...")
            # Check what's actually in experiments table
            all_exp_details = DB.query_all("SELECT session_id, name, timestamp FROM experiments", ())
            print(f"DEBUG: All experiment details: {all_exp_details}")
            raise AssertionError(f"No experiment found for session_id {shim.session_id}")
            
        graph = json.loads(graph_topology["graph_topology"])
    except Exception as e:
        # Print server logs for debugging when test fails
        import subprocess
        print("\n" + "="*80)
        print("SERVER LOGS (for debugging):")
        print("="*80)
        try:
            result = subprocess.run(
                ["aco-server", "logs"],
                capture_output=True,
                text=True,
                timeout=5
            )
            print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
        except Exception as log_error:
            print(f"Failed to retrieve server logs: {log_error}")
        print("="*80 + "\n")
        raise e

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
