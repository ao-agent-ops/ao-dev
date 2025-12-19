# Wrapper script templates for launching user code with AST rewrites and environment setup.
# These templates use placeholders that will be replaced by develop_shim.py.


_SETUP_TRACING_SETUP = """import os
import sys
import runpy
import socket
import json
import random
import builtins
import warnings
from aco.runner.ast_rewrite_hook import install_patch_hook, set_module_to_user_file
from aco.runner.context_manager import set_parent_session_id, set_server_connection
from aco.common.constants import HOST, PORT, SOCKET_TIMEOUT
from aco.common.utils import scan_user_py_files_and_modules
from aco.common.logger import logger
from aco.runner.monkey_patching.apply_monkey_patches import apply_all_monkey_patches
from aco.server.ast_transformer import (
    taint_fstring_join, taint_format_string, taint_percent_format, exec_func
)
from aco.server.database_manager import DB


module_to_file = {module_to_file}

# Install the hooks for AST re-writing
set_module_to_user_file(module_to_file)
install_patch_hook()

# Register taint functions in builtins so rewritten .pyc files can call them
builtins.taint_fstring_join = taint_fstring_join
builtins.taint_format_string = taint_format_string
builtins.taint_percent_format = taint_percent_format
builtins.exec_func = exec_func

# Connect to server and apply monkey patches if enabled via environment variable.
if os.environ.get("AGENT_COPILOT_ENABLE_TRACING"):
    host = os.environ.get("AGENT_COPILOT_SERVER_HOST", HOST)
    port = int(os.environ.get("AGENT_COPILOT_SERVER_PORT", PORT))
    session_id = os.environ.get("AGENT_COPILOT_SESSION_ID")
    server_conn = None

    # Connect to server, this will be the global server connection for the process.
    # We currently rely on the OS to close the connection when proc finishes.
    server_conn = socket.create_connection((host, port), timeout=SOCKET_TIMEOUT)

    # Handshake. Send hello and wait for server acknowledgment.
    handshake = {{
        "type": "hello",
        "role": "shim-runner",
        "script": os.path.basename(os.environ.get("_", "unknown")),
        "process_id": os.getpid(),
    }}
    server_conn.sendall((json.dumps(handshake) + "\\n").encode("utf-8"))
    
    # Wait for server acknowledgment and get which DB to use
    ready_response = server_conn.makefile("r").readline()
    ready_msg = json.loads(ready_response.strip())
    database_mode = ready_msg.get("database_mode")    
    DB.switch_mode(database_mode)

    # Register session_id and connection with context manager.
    set_parent_session_id(session_id)
    set_server_connection(server_conn)

    # Apply monkey patches.
    apply_all_monkey_patches()

    # Set random seeds
    aco_random_seed = os.environ.get("ACO_SEED", None)
    if not aco_random_seed:
        raise Exception("ACO random seed not set.")
    else:
        try:
            aco_random_seed = int(aco_random_seed)
        except:
            raise Exception("Error converting ACO_SEED to int.")
    logger.debug(f"ACO_SEED was set to {{aco_random_seed}}")
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", module="numpy")
            from numpy.random import seed
            seed(aco_random_seed)
    except:
        logger.debug("Failed to set the numpy seed")
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", module="torch")
            from torch import manual_seed
            manual_seed(aco_random_seed)
    except:
        logger.debug("Failed to set the torch seed")
    random.seed(aco_random_seed)
"""


# Template for running a script as a module (when user runs: develop script.py)
SCRIPT_WRAPPER_TEMPLATE = (
    _SETUP_TRACING_SETUP
    + """
# Set up argv and run the module
sys.argv = [{module_name}] + {script_args}
runpy.run_module({module_name}, run_name='__main__')
"""
)

# Template for running a module directly (when user runs: develop -m module)
MODULE_WRAPPER_TEMPLATE = (
    _SETUP_TRACING_SETUP
    + """
# Now run the module with proper resolution
sys.argv = [{module_name}] + {script_args}
runpy.run_module({module_name}, run_name='__main__')
"""
)
