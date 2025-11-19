import inspect
import textwrap
import os
from datetime import datetime
from aco.server.ast_transformer import rewrite_source_to_code
from aco.server.database_manager import DB
from aco.server.edit_manager import EDIT


def cleanup_taint_db():
    """Clean up all taint information from the database and environment"""
    import os

    # Ensure we're using local SQLite for tests
    DB.switch_mode("local")

    # Clear all taint records
    DB.execute("DELETE FROM attachments")

    # Clean up environment variables that affect taint tracking
    if "AGENT_COPILOT_SESSION_ID" in os.environ:
        del os.environ["AGENT_COPILOT_SESSION_ID"]


def setup_test_session(session_id, name="Test Session", parent_session_id=None):
    """
    Helper to create necessary database records for testing.
    
    This is a simplified approach that directly creates the experiment record
    in the database. A more thorough approach would be to:
    
    1. Start a test server instance or mock the server connection
    2. Simulate the full handshake flow from launch_scripts.py:
       - Send "hello" message with role="shim-runner"  
       - Server creates experiment record
       - Server responds with acknowledgment
    3. Use the actual monkey-patched flow for LLM calls
    4. File operations go through TaintFile which communicates with server
    
    That approach would test the entire integration including server message
    handling, protocol, and session management, but would be more complex
    to set up and maintain.
    
    Args:
        session_id: The session ID to create
        name: Name for the test session
        parent_session_id: Parent session ID (defaults to session_id if None)
    """
    # Ensure we're using local SQLite for tests
    DB.switch_mode("local")
    
    EDIT.add_experiment(
        session_id=session_id,
        name=name,
        timestamp=datetime.now(),
        cwd=os.getcwd(),
        command="test",
        environment={"TEST": "true"},
        parent_session_id=parent_session_id or session_id
    )


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
