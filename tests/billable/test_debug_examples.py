import asyncio
import pytest

try:
    from tests.billable.caching_utils import run_test, caching_asserts
except ImportError:
    from caching_utils import run_test, caching_asserts


@pytest.mark.parametrize(
    "script_path",
    [
        "./example_workflows/debug_examples/langchain_agent.py",
        "./example_workflows/debug_examples/langchain_async_agent.py",
        "./example_workflows/debug_examples/langchain_simple_chat.py",
        "./example_workflows/debug_examples/together_add_numbers.py",
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
    run_data_obj = asyncio.run(run_test(script_path=script_path, project_root="."))
    caching_asserts(run_data_obj)


if __name__ == "__main__":
    test_debug_examples("./example_workflows/debug_examples/anthropic_add_numbers.py")
