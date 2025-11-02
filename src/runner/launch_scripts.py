# Wrapper script templates for launching user code with AST rewrites and environment setup.
# These templates use placeholders that will be replaced by develop_shim.py.


_SETUP_TRACING_SETUP = """import os
import sys
import runpy
import socket
import json
import traceback
from aco.common.logger import logger


project_root = {project_root}
packages_in_project_root = {packages_in_project_root}

# Add project root to path
# FIXME: This is a bit hacky so we are able to import the 
# user's modules. I'm not sure this is needed but even if,
# it's probably not a good way to do this.
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from aco.runner.patching_import_hook import install_patch_hook, set_module_to_user_file

# Rewrite AST to support f-strings
from aco.common.utils import scan_user_py_files_and_modules

_, _, module_to_file = scan_user_py_files_and_modules(project_root)
for additional_package in packages_in_project_root:
    _, _, additional_package_module_to_file = scan_user_py_files_and_modules(additional_package)
    module_to_file = {{**module_to_file, **additional_package_module_to_file}}

set_module_to_user_file(module_to_file)
install_patch_hook()

# Connect to server and pply monkey patches if enabled via environment variable.
from aco.runner.context_manager import set_parent_session_id, set_server_connection
from aco.common.constants import HOST, PORT, SOCKET_TIMEOUT
from aco.runner.monkey_patching.apply_monkey_patches import apply_all_monkey_patches

if os.environ.get("AGENT_COPILOT_ENABLE_TRACING"):
    host = os.environ.get("AGENT_COPILOT_SERVER_HOST", HOST)
    port = int(os.environ.get("AGENT_COPILOT_SERVER_PORT", PORT))
    session_id = os.environ.get("AGENT_COPILOT_SESSION_ID")
    server_conn = None
    # try:
    # Connect to server, this will be the global server connection for the process.
    # We currently rely on the OS to close the connection when proc finishes.
    server_conn = socket.create_connection((host, port), timeout=SOCKET_TIMEOUT)

    # Handshake. For shim-runner, server doesn't send a response, just start running.
    handshake = {{
        "type": "hello",
        "role": "shim-runner",
        "script": os.path.basename(os.environ.get("_", "unknown")),
        "process_id": os.getpid(),
    }}
    server_conn.sendall((json.dumps(handshake) + "\\n").encode("utf-8"))

    # Register session_id and connection with context manager.
    set_parent_session_id(session_id)
    set_server_connection(server_conn)

    # except Exception as e:
    #     logger.error(f"Exception set up tracing:")
    #     traceback.print_exc()

    # Apply monkey patches.
    apply_all_monkey_patches()
"""


# Template for running a script as a module (when user runs: develop script.py)
SCRIPT_WRAPPER_TEMPLATE = (
    _SETUP_TRACING_SETUP
    + """
# Set up argv and run the module
module_name = os.path.abspath({module_name})
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
