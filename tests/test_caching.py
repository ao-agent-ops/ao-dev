"""
Tests for caching and restart functionality.

These tests verify that:
1. LLM calls are properly cached and replayed on re-runs
2. Graph topology is preserved across runs
3. Node IDs remain consistent for cache hits
"""

import json
import os
import subprocess
import sys
import pytest
from dataclasses import dataclass
from ao.server.database_manager import DB

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


def run_script_via_ao_launch(script_path: str, project_root: str) -> str:
    """
    Run a script using ao-launch and return the session_id.

    Args:
        script_path: Path to the script to run
        project_root: Project root directory

    Returns:
        The session_id from the experiment record
    """
    env = os.environ.copy()
    env["ao_DATABASE_MODE"] = "local"

    # Run the script via ao-launch
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ao.cli.ao_launch",
            "--project-root",
            project_root,
            script_path,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise RuntimeError(f"Script failed with return code {result.returncode}")

    # Query for the most recent experiment to get session_id
    # The experiment was just created, so it should be the most recent one
    experiment = DB.query_one("SELECT session_id FROM experiments ORDER BY timestamp DESC LIMIT 1")
    if not experiment:
        raise RuntimeError("No experiment found in database after running script")

    return experiment["session_id"]


def run_test(script_path: str, project_root: str) -> RunData:
    """
    Run a script twice and collect data for comparison.

    First run: Execute script normally
    Second run: Execute again (should use cache)

    Returns:
        RunData with rows and graph data from both runs
    """
    # Restart server to ensure clean state
    restart_server()

    # Ensure we're using local SQLite
    DB.switch_mode("local")

    # First run
    session_id = run_script_via_ao_launch(script_path, project_root)

    rows = DB.query_all(
        "SELECT node_id, input_overwrite, output FROM llm_calls WHERE session_id=?",
        (session_id,),
    )

    graph_topology = DB.query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
        (session_id,),
    )
    graph = json.loads(graph_topology["graph_topology"])

    # Second run (should use cache)
    # We need to set the session ID so the new run uses the same cache
    env = os.environ.copy()
    env["AO_DATABASE_MODE"] = "local"
    env["AGENT_COPILOT_SESSION_ID"] = session_id

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ao.cli.ao_launch",
            "--project-root",
            project_root,
            script_path,
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise RuntimeError(f"Re-run failed with return code {result.returncode}")

    new_rows = DB.query_all(
        "SELECT node_id, input_overwrite, output FROM llm_calls WHERE session_id=?",
        (session_id,),
    )

    new_graph_topology = DB.query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=?",
        (session_id,),
    )
    new_graph = json.loads(new_graph_topology["graph_topology"])

    return RunData(rows=rows, new_rows=new_rows, graph=graph, new_graph=new_graph)


def _caching_asserts(run_data_obj: RunData):
    assert len(run_data_obj.rows) == len(
        run_data_obj.new_rows
    ), f"Length of LLM calls does not match after re-run{len(run_data_obj.rows)} vs {len(run_data_obj.new_rows)}"
    for old_row, new_row in zip(run_data_obj.rows, run_data_obj.new_rows):
        assert (
            old_row["node_id"] == new_row["node_id"]
        ), "Node IDs of LLM calls don't match after re-run. Potential cache issue."

    # Compare graph topology between runs
    assert len(run_data_obj.graph["nodes"]) == len(
        run_data_obj.new_graph["nodes"]
    ), f"Number of nodes in graph topology doesn't match after re-run: first: {len(run_data_obj.graph["nodes"])} vs. second: {len(
        run_data_obj.new_graph["nodes"]
    )}"
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
    run_data_obj = run_test(
        script_path="./example_workflows/miroflow_deep_research/single_task.py",
        project_root="./example_workflows/miroflow_deep_research",
    )
    _caching_asserts(run_data_obj)
    _deepresearch_asserts(run_data_obj)


@pytest.mark.parametrize(
    "script_path",
    [
        "./example_workflows/debug_examples/langchain_agent.py",
        "./example_workflows/debug_examples/langchain_async_agent.py",
        "./example_workflows/debug_examples/langchain_simple_chat.py",
        # "./example_workflows/debug_examples/together_add_numbers.py",
        "./example_workflows/debug_examples/anthropic_image_tool_call.py",
        "./example_workflows/debug_examples/anthropic_async_add_numbers.py",
        "./example_workflows/debug_examples/anthropic_add_numbers.py",
        "./example_workflows/debug_examples/mcp_simple_test.py",
        "./example_workflows/debug_examples/multiple_runs_asyncio.py",
        "./example_workflows/debug_examples/multiple_runs_sequential.py",
        "./example_workflows/debug_examples/multiple_runs_threading.py",
        "./example_workflows/debug_examples/openai_async_add_numbers.py",
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
    run_data_obj = run_test(
        script_path=script_path, project_root="./example_workflows/debug_examples"
    )
    _caching_asserts(run_data_obj)


if __name__ == "__main__":
    test_deepresearch()
