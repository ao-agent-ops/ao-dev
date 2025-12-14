import os
import json
import subprocess
import sys
import socket
import time
import shutil
from aco.server.database_manager import DB

# Add tests directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import restart_server


def switch_to_cheap_model():
    """Switch to gpt-4o-mini for testing and return the original model name."""
    # Get absolute path to config file relative to this test file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(
        script_dir,
        "..",
        "..",
        "example_workflows",
        "miroflow_deep_research",
        "config",
        "llm",
        "default.yaml",
    )
    backup_path = config_path + ".backup"

    # Read current config
    with open(config_path, "r") as f:
        content = f.read()

    # Backup original config
    shutil.copy2(config_path, backup_path)

    # Find current model name for restoration
    original_model = None
    for line in content.split("\n"):
        if line.strip().startswith("model_name:"):
            original_model = line.strip().split('"')[1]
            break

    # Replace with gpt-4o-mini
    new_content = content.replace(f'model_name: "{original_model}"', 'model_name: "gpt-4o-mini"')

    # Write updated config
    with open(config_path, "w") as f:
        f.write(new_content)

    print(f"[Test] Temporarily switched model from {original_model} to gpt-4o-mini")
    return original_model


def restore_original_model():
    """Restore the original model configuration."""
    # Get absolute path to config file relative to this test file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(
        script_dir,
        "..",
        "..",
        "example_workflows",
        "miroflow_deep_research",
        "config",
        "llm",
        "default.yaml",
    )
    backup_path = config_path + ".backup"

    if os.path.exists(backup_path):
        # Restore original config
        shutil.move(backup_path, config_path)
        print("[Test] Restored original model configuration")
    else:
        print("[Test] Warning: No backup found to restore")


def run_aco_launch(script_path):
    """Run aco-launch command and return the session_id from DB."""
    # Get absolute path to miroflow_deep_research directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    miroflow_dir = os.path.join(
        script_dir, "..", "..", "example_workflows", "miroflow_deep_research"
    )

    # Run aco-launch command normally - let it handle everything
    cmd = [sys.executable, "-m", "aco.cli.aco_launch", script_path]
    result = subprocess.run(cmd, cwd=miroflow_dir, capture_output=False, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr and result.returncode != 0:
        print(result.stderr, file=sys.stderr)

    # Get the most recent session_id from database
    # Since we just ran the script, the latest session should be ours
    recent_session = DB.query_one(
        "SELECT session_id FROM experiments ORDER BY timestamp DESC LIMIT 1"
    )
    session_id = recent_session["session_id"] if recent_session else None

    return result.returncode, session_id


def main():
    # Restart server to ensure clean state for this test
    restart_server()

    # Set database mode before running
    DB.switch_mode("local")

    # Switch to cheaper model for testing
    original_model = switch_to_cheap_model()

    # Step 1: Run the actual deep research script normally
    return_code, session_id = run_aco_launch("single_task.py")
    assert return_code == 0, f"[DeepResearch] failed with return_code {return_code}"
    assert session_id, "No session_id found in database after first run"

    print("~~~~ session_id", session_id)

    # Step 2: Query first run results
    rows = DB.query_all(
        "SELECT node_id, input_overwrite, output FROM llm_calls WHERE session_id=?",
        (session_id,),
    )

    graph_topology = DB.query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
        (session_id,),
    )
    graph = json.loads(graph_topology["graph_topology"])

    print("\n\n", "=" * 20, " triggering restart ", "=" * 20, "\n\n")

    # Step 3: Connect to server and send restart message
    from aco.common.constants import HOST, PORT

    server_conn = socket.create_connection((HOST, PORT), timeout=10)

    # Send restart message (same as old test)
    restart_message = {"type": "restart", "session_id": session_id}
    server_conn.sendall((json.dumps(restart_message) + "\n").encode("utf-8"))

    # Wait for restart to process
    time.sleep(2)

    server_conn.close()

    # Step 4: Wait for rerun to complete and query results
    # Poll the database to detect when the rerun has completed
    start_time = time.time()
    timeout = 60  # 60 second timeout

    print("Waiting for rerun to complete...")

    while time.time() - start_time < timeout:
        # Check if new LLM calls have been added (rerun completed)
        current_rows = DB.query_all(
            "SELECT node_id, input_overwrite, output FROM llm_calls WHERE session_id=?",
            (session_id,),
        )

        # If we have more rows than before, or the graph has been updated, rerun is complete
        if len(current_rows) >= len(rows):
            current_graph = DB.query_one(
                "SELECT graph_topology FROM experiments WHERE session_id=?",
                (session_id,),
            )
            if current_graph:
                current_graph_obj = json.loads(current_graph["graph_topology"])
                if len(current_graph_obj["nodes"]) > 0:
                    break

        time.sleep(0.5)

    else:
        raise TimeoutError("Rerun did not complete within 60 seconds")

    print("Rerun completed, checking results...")

    # Step 5: Query second run results
    new_rows = DB.query_all(
        "SELECT node_id, input_overwrite, output FROM llm_calls WHERE session_id=?",
        (session_id,),
    )

    new_graph_topology = DB.query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
        (session_id,),
    )
    new_graph = json.loads(new_graph_topology["graph_topology"])

    print("~~~~ first run had", len(rows), "LLM calls")
    print("~~~~ second run had", len(new_rows), "LLM calls")

    # Step 6: Compare results (same assertions as old test)
    assert len(rows) == len(
        new_rows
    ), f"[DeepResearch] Length of LLM calls does not match after re-run. First run: {len(rows)}, Second run: {len(new_rows)}"

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

    print("[DeepResearch] All assertions passed! Reproducibility test successful.")

    # Restore original model configuration
    restore_original_model()


def test_deepresearch():
    main()


if __name__ == "__main__":
    test_deepresearch()
