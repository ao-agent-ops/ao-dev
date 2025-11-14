import inspect
import textwrap
from aco.server.ast_transformer import rewrite_source_to_code
from aco.server.db import execute


def cleanup_taint_db():
    """Clean up all taint information from the database and environment"""
    import os

    # Clear all taint records
    execute("DELETE FROM attachments")

    # Clean up environment variables that affect taint tracking
    if "AGENT_COPILOT_SESSION_ID" in os.environ:
        del os.environ["AGENT_COPILOT_SESSION_ID"]


def with_ast_rewriting(test_func):
    """
    Decorator to execute a test function with AST rewriting.

    This decorator:
    1. Extracts the source code of the test function body
    2. Applies AST transformation for taint tracking
    3. Executes the transformed code
    4. If execution succeeds, the test passes
    5. If execution raises an exception, re-raises it

    Usage:
        @with_ast_rewriting
        def test_something(self):
            # Test code here will be executed with AST rewriting
            result = json.loads(tainted_data)
            assert isinstance(result, TaintDict)
    """

    def wrapper(*args, **kwargs):
        # Get the source code of the function
        source_lines = inspect.getsourcelines(test_func)[0]

        # Find the start of the function body (after the def line and docstring)
        body_start = 1  # Skip the def line

        # Skip docstring if present
        if len(source_lines) > 1 and ('"""' in source_lines[1] or "'''" in source_lines[1]):
            # Find end of docstring
            for i in range(body_start + 1, len(source_lines)):
                if '"""' in source_lines[i] or "'''" in source_lines[i]:
                    body_start = i + 1
                    break

        # Extract and dedent the function body
        body_lines = source_lines[body_start:]
        body_source = textwrap.dedent("".join(body_lines))

        # Apply AST transformation
        code_object = rewrite_source_to_code(
            body_source, f"<{test_func.__name__}>", module_to_file={}
        )

        # Execute the transformed code using caller's globals
        exec(code_object, globals())

    return wrapper
