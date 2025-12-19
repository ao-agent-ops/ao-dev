import asyncio

try:
    from tests.billable.caching_utils import run_test, caching_asserts, RunData
except ImportError:
    from caching_utils import run_test, caching_asserts, RunData


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
    caching_asserts(run_data_obj)
    _deepresearch_asserts(run_data_obj)


if __name__ == "__main__":
    test_deepresearch()
