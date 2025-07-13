import os
import socket
import json
import traceback
from common.logging_config import setup_logging
logger = setup_logging()

import os
from runtime_tracing.fstring_rewriter import install_fstring_rewriter, set_user_py_files

def scan_user_py_files_and_modules(root_dir):
    user_py_files = set()
    file_to_module = dict()
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.py'):
                abs_path = os.path.abspath(os.path.join(dirpath, filename))
                user_py_files.add(abs_path)
                # Compute module name relative to root_dir
                rel_path = os.path.relpath(abs_path, root_dir)
                mod_name = rel_path[:-3].replace(os.sep, '.')  # strip .py, convert / to .
                if mod_name.endswith(".__init__"):
                    mod_name = mod_name[:-9]  # remove .__init__
                file_to_module[abs_path] = mod_name
    return user_py_files, file_to_module

# Scan for all .py files in the current working directory (workspace root)
user_py_files, file_to_module = scan_user_py_files_and_modules("/Users/ferdi/Documents/agent-copilot")
print(f"[DEBUG] Found {len(user_py_files)} Python files")
print(f"[DEBUG] File to module mapping:")
for file_path, mod_name in file_to_module.items():
    print(f"  {mod_name}: {file_path}")
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
        try:
            from runtime_tracing.apply_monkey_patches import apply_all_monkey_patches
            from runtime_tracing.monkey_patches import set_session_id
            print(f"[DEBUG] sitecustomize: session_id from env = {session_id}")
            if session_id:
                set_session_id(session_id)
                print(f"[DEBUG] sitecustomize: set_session_id called with {session_id}")
            else:
                print(f"[DEBUG] sitecustomize: No session_id in environment, not setting")
            apply_all_monkey_patches(server_conn)
        except Exception as e:
            logger.error(f"Exception in sitecustomize.py patching: {e}")
            traceback.print_exc()

setup_tracing() 