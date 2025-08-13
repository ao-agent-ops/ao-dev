import os
import socket
import json
import traceback
from agent_copilot.context_manager import set_parent_session_id, set_server_connection
from common.logger import logger
from common.constants import HOST, PORT, SOCKET_TIMEOUT
from runtime_tracing.apply_monkey_patches import apply_all_monkey_patches


def setup_tracing():
    """
    Set up runtime tracing if enabled via environment variable.
    """
    if not os.environ.get("AGENT_COPILOT_ENABLE_TRACING"):
        return
    host = os.environ.get("AGENT_COPILOT_SERVER_HOST", HOST)
    port = int(os.environ.get("AGENT_COPILOT_SERVER_PORT", PORT))
    session_id = os.environ.get("AGENT_COPILOT_SESSION_ID")
    server_conn = None
    try:
        # Connect to server, this will be the global server connection for the process.
        # We currently rely on the OS to close the connection when proc finishes.
        server_conn = socket.create_connection((host, port), timeout=SOCKET_TIMEOUT)

        # Handshake. For shim-runner, server doesn't send a response, just start running.
        handshake = {
            "type": "hello",
            "role": "shim-runner",
            "script": os.path.basename(os.environ.get("_", "unknown")),
            "process_id": os.getpid(),
        }
        server_conn.sendall((json.dumps(handshake) + "\n").encode("utf-8"))

        # Register session_id and connection with context manager.
        set_parent_session_id(session_id)
        set_server_connection(server_conn)

        # Apply monkey patches.
        apply_all_monkey_patches()
    except Exception as e:
        logger.error(f"Exception in sitecustomize.py: {e}")
        traceback.print_exc()
