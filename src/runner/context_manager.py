import contextvars
from contextlib import contextmanager
import json
import threading
import os
from aco.common.logger import logger
from aco.server.cache_manager import CACHE
from aco.common.utils import send_to_server, send_to_server_and_receive


# Process's session id stored as parent_session_id. Subruns have their own
# session_id and current_session_id maps thread -> session_id.
current_session_id = contextvars.ContextVar("session_id", default=None)
parent_session_id = None

# Connection to server, which is shared throughout the process.
server_conn = None
server_file = None

# Names of all subruns in the process. Used to ensure they are unique.
run_names = None


def get_run_name(run_name):
    logger.debug(f"Active runs in run_names set: {run_names}")
    # Run names must be unique for a given parent_session_id.
    if run_name not in run_names:
        run_names.add(run_name)
        return run_name

    i = 1
    while f"{run_name} ({i})" in run_names:
        i += 1

    run_name = f"{run_name} ({i})"
    run_names.add(run_name)
    return run_name


@contextmanager
def aco_launch(run_name="Workflow run"):
    """
    Context manager for launching runs with a specific name.
    NOTE: Upon rerun of one subrun, we rerun all subruns. Other
    subruns' expensive calls should be cached though. We also
    hide this somewhat in the UI.

    Args:
        run_name (str): Name of the run to launch

    Usage:
        with aco_launch(run_name="my_eval"):
            # User code runs here
            result = some_function()
    """
    # Get unique run name.
    run_name = get_run_name(run_name)
    logger.debug(
        f"Sub-run '{run_name}' starting in process {os.getpid()}, thread {threading.get_ident()}"
    )

    # Get rerun environment from parent
    # BUG: If parent sets env vars before calling this, these env vars are lost upon restart.
    parent_env = CACHE.get_parent_environment(parent_session_id)

    # If rerun, get previous's runs session_id, else None.
    prev_session_id = CACHE.get_subrun_id(parent_session_id, run_name)

    # Register new subrun with server.
    msg = {
        "type": "add_subrun",
        "name": run_name,
        "parent_session_id": parent_session_id,
        "cwd": parent_env["cwd"],
        "command": parent_env["command"],
        "environment": json.loads(parent_env["environment"]),
        "prev_session_id": prev_session_id,
    }
    response = send_to_server_and_receive(msg)
    session_id = response["session_id"]
    current_session_id.set(session_id)

    try:
        # Run user code
        yield run_name
    finally:
        # Deregister
        deregister_msg = {"type": "deregister", "session_id": session_id}
        send_to_server(deregister_msg)


def log(entry=None, success=None):
    # Validate input types
    if entry is not None and not isinstance(entry, str):
        raise TypeError(f"`entry` must be a string, got {type(entry).__name__}")
    if success is not None and not isinstance(success, bool):
        raise TypeError(f"`success` must be a boolean or None, got {type(success).__name__}")

    # Send to server.
    server_file.write(
        json.dumps(
            {"type": "log", "session_id": get_session_id(), "success": success, "entry": entry}
        )
        + "\n"
    )
    server_file.flush()


def get_session_id():
    sid = current_session_id.get()
    assert sid is not None
    return sid


def set_parent_session_id(session_id):
    # Called by sitecustomize.py: set session id of `aco-launch`
    global parent_session_id, current_session_id, run_names
    parent_session_id = session_id
    current_session_id.set(session_id)
    run_names = set(CACHE.get_session_name(parent_session_id))


def set_server_connection(server_connection):
    global server_conn, server_file
    server_conn = server_connection
    server_file = server_connection.makefile("rw")
    logger.debug(f"Set server connection in context_manager")
