import contextvars
from contextlib import contextmanager
import json
import socket
import threading
import os

from workflow_edits.cache_manager import CACHE
from workflow_edits.edit_manager import EDIT
from common.logger import logger

# Context variables to store the current session_id
current_session_id = contextvars.ContextVar("session_id", default=None)
parent_session_id = None


@contextmanager
def aco_launch(run_name="Workflow run"):
    """
    Context manager for launching runs with a specific name.
    NOTE: We need to rerun all subruns if we use a context manager.
    Other subruns' expensive calls should be cached though. We also
    hide this somewhat in the UI.

    Args:
        run_name (str): Name of the run to launch

    Usage:
        with aco_launch(run_name="my_eval"):
            # User code runs here
            result = some_function()
    """
    logger.debug(
        f"Sub-run '{run_name}' starting in process {os.getpid()}, thread {threading.get_ident()}"
    )

    # Get rerun environment from parent
    # BUG: If parent sets env vars before calling this, these env vars are lost upon restart.
    parent_env = CACHE.get_parent_environment(parent_session_id)

    # If rerun, get previous's runs session_id.
    prev_session_id = CACHE.get_subrun_id(parent_session_id, run_name)

    # Register with server as shim-control.
    shim_sock = socket.create_connection(("127.0.0.1", 5959))
    shim_file = shim_sock.makefile("rw")
    handshake = {
        "type": "hello",
        "role": "shim-control",
        "name": run_name,
        "parent_session_id": parent_session_id,
        "cwd": parent_env["cwd"],
        "command": parent_env["command"],
        "environment": json.loads(parent_env["environment"]),
        "prev_session_id": prev_session_id,
    }
    shim_file.write(json.dumps(handshake) + "\n")
    shim_file.flush()

    # Get newly assigned session id (== previous one if it's a rerun).
    response = json.loads(shim_file.readline().strip())
    session_id = response["session_id"]
    token = current_session_id.set(session_id)

    # Run user code
    try:
        yield run_name
    finally:
        # Clean up
        deregister_msg = {"type": "deregister", "session_id": session_id}
        shim_file.write(json.dumps(deregister_msg) + "\n")
        shim_file.flush()
        shim_sock.close()
        current_session_id.reset(token)


def get_session_id():
    sid = current_session_id.get()
    assert sid is not None
    return sid


def set_session_id(session_id):
    # Called by sitecustomize.py: set session id of `aco-launch`
    global parent_session_id, current_session_id
    assert session_id is not None
    parent_session_id = session_id
    current_session_id.set(session_id)
