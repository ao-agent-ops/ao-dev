import os
import socket
import json
import traceback
from common.logger import logger
from common.constants import ACO_PROJECT_ROOT, HOST, PORT, SOCKET_TIMEOUT
from runtime_tracing.fstring_rewriter import install_fstring_rewriter, set_user_py_files
from common.utils import scan_user_py_files_and_modules
from runtime_tracing.apply_monkey_patches import apply_all_monkey_patches
from runtime_tracing.monkey_patches import set_session_id

user_py_files, file_to_module = scan_user_py_files_and_modules(ACO_PROJECT_ROOT)
set_user_py_files(user_py_files, file_to_module)

install_fstring_rewriter()

def setup_tracing():
    """
    Set up runtime tracing if enabled via environment variable.
    """
    if not os.environ.get('AGENT_COPILOT_ENABLE_TRACING'):
        return
    host = os.environ.get('AGENT_COPILOT_SERVER_HOST', HOST)
    port = int(os.environ.get('AGENT_COPILOT_SERVER_PORT', PORT))
    session_id = os.environ.get('AGENT_COPILOT_SESSION_ID')
    server_conn = None
    try:
        server_conn = socket.create_connection((host, port), timeout=SOCKET_TIMEOUT)
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
            file_obj = server_conn.makefile(mode='r')
            session_line = file_obj.readline()
            if session_line:
                try:
                    session_msg = json.loads(session_line.strip())
                    # session_id = session_msg.get("session_id")  # Don't override env session_id
                except Exception:
                    pass
        except Exception:
            pass
        try:            # print(f"[DEBUG] sitecustomize: session_id from env = {session_id}")
            if session_id:
                set_session_id(session_id)
                # print(f"[DEBUG] sitecustomize: set_session_id called with {session_id}")
            else:
                logger.error(f"sitecustomize: No session_id in environment, run will not be traced properly.")
            apply_all_monkey_patches(server_conn)
        except Exception as e:
            logger.error(f"Exception in sitecustomize.py patching: {e}")
            traceback.print_exc()

setup_tracing() 