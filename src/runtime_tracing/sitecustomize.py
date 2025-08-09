import os
import socket
import json
import traceback
from common.logger import logger

import os
from runtime_tracing.fstring_rewriter import install_fstring_rewriter, set_user_py_files
from common.utils import get_project_root, scan_user_py_files_and_modules
from runtime_tracing.apply_monkey_patches import apply_all_monkey_patches
from runtime_tracing.monkey_patches import set_session_id

user_py_files, file_to_module = scan_user_py_files_and_modules(get_project_root())
set_user_py_files(user_py_files, file_to_module)

install_fstring_rewriter()

def setup_tracing():
    """
    Set up runtime tracing if enabled via environment variable.
    """
    if not os.environ.get('AGENT_COPILOT_ENABLE_TRACING'):
        return
    host = os.environ.get('AGENT_COPILOT_SERVER_HOST', '127.0.0.1')
    port = int(os.environ.get('AGENT_COPILOT_SERVER_PORT', '5959'))
    session_id = os.environ.get('AGENT_COPILOT_SESSION_ID')
    server_conn = None
    try:
        server_conn = socket.create_connection((host, port), timeout=5)
    except Exception:
        return
    if server_conn:
        handshake = {
            "type": "hello",
            "role": "shim-runner",
            "script": os.path.basename(os.environ.get('_', 'unknown')),
            "process_id": os.getpid()
        }
        try:
            server_conn.sendall((json.dumps(handshake) + "\n").encode('utf-8'))
            # For shim-runner, server doesn't send a response, so don't wait for one
        except Exception:
            pass
        try:
            if session_id:
                set_session_id(session_id)
            else:
                logger.error(f"sitecustomize: No session_id in environment, run will not be traced properly.")
            apply_all_monkey_patches(server_conn)
        except Exception as e:
            logger.error(f"Exception in sitecustomize.py patching: {e}")
            traceback.print_exc()

setup_tracing() 