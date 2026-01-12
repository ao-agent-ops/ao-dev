import inspect
import textwrap
import os
from datetime import datetime
from ao.server.file_watcher import rewrite_source_to_code
from ao.server.database_manager import DB


def cleanup_taint_db():
    """Clean up all taint information from the database and environment"""
    import os

    # Ensure we're using local SQLite for tests
    DB.switch_mode("local")

    # Clear all taint records
    DB.execute("DELETE FROM attachments")

    # Clean up environment variables that affect taint tracking
    if "AO_SESSION_ID" in os.environ:
        del os.environ["AO_SESSION_ID"]


def restart_server():
    """Restart the server to ensure clean state for tests."""
    import subprocess
    import time

    subprocess.run(["ao-server", "restart"], check=False)
    time.sleep(1)


def setup_test_session(session_id, name="Test Session", parent_session_id=None):
    """
    Helper to create necessary database records for testing.

    This is a simplified approach that directly creates the experiment record
    in the database. A more thorough approach would be to:

    1. Start a test server instance or mock the server connection
    2. Simulate the full handshake flow from agent_runner.py:
       - Send "hello" message with role="agent-runner"
       - Server creates experiment record
       - Server responds with acknowledgment
    3. Use the actual monkey-patched flow for LLM calls
    4. File operations go through taint_open which communicates with server

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

    DB.add_experiment(
        session_id=session_id,
        name=name,
        timestamp=datetime.now(),
        cwd=os.getcwd(),
        command="test",
        environment={"TEST": "true"},
        parent_session_id=parent_session_id or session_id,
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
            assert get_taint(result) != []
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
            body_source, f"<{test_func.__name__}>", user_files=set()
        )

        # Set up the taint environment (normally done by agent_runner)
        import builtins
        from ao.runner.taint_containers import ThreadSafeTaintDict, TaintStack

        # Initialize TAINT_STACK for passing taint through third-party code
        builtins.TAINT_STACK = TaintStack()

        # Initialize TAINT_DICT (id-based dict) as single source of truth
        # Always create fresh TAINT_DICT for each test to avoid cross-test contamination
        builtins.TAINT_DICT = ThreadSafeTaintDict()

        # Add taint functions to builtins (normally done by agent_runner)
        from ao.server.taint_ops import (
            taint_fstring_join,
            taint_format_string,
            taint_percent_format,
            taint_open,
            exec_func,
            exec_setitem,
            exec_delitem,
            exec_inplace_binop,
            taint_assign,
            get_attr,
            get_item,
            set_attr,
            add_to_taint_dict_and_return,
            get_taint,
        )

        builtins.taint_fstring_join = taint_fstring_join
        builtins.taint_format_string = taint_format_string
        builtins.taint_percent_format = taint_percent_format
        builtins.taint_open = taint_open
        builtins.exec_func = exec_func
        builtins.exec_setitem = exec_setitem
        builtins.exec_delitem = exec_delitem
        builtins.exec_inplace_binop = exec_inplace_binop
        builtins.taint_assign = taint_assign
        builtins.get_attr = get_attr
        builtins.get_item = get_item
        builtins.set_attr = set_attr
        builtins.add_to_taint_dict_and_return = add_to_taint_dict_and_return
        builtins.get_taint = get_taint

        # Execute the transformed code using test function's globals
        test_globals = test_func.__globals__.copy()
        test_globals.update(globals())  # Add utils globals for any dependencies

        exec(code_object, test_globals)

    return wrapper


def with_ast_rewriting_class(cls):
    """
    Class decorator that applies @with_ast_rewriting to all test methods in a class.

    Usage:
        @with_ast_rewriting_class
        class TestSomething:
            def test_method(self):
                # This will be executed with AST rewriting
                pass
    """
    for attr_name in dir(cls):
        if attr_name.startswith("test_") and callable(getattr(cls, attr_name)):
            original_method = getattr(cls, attr_name)
            decorated_method = with_ast_rewriting(original_method)
            setattr(cls, attr_name, decorated_method)
    return cls
