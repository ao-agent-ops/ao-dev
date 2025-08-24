import asyncio
import inspect
import functools
import threading
import functools
from agent_copilot.context_manager import get_session_id
from common.constants import CERTAINTY_GREEN, CERTAINTY_RED, CERTAINTY_YELLOW
from common.utils import send_to_server
from workflow_edits.cache_manager import CACHE
from common.logger import logger
from workflow_edits.utils import get_input, get_model_name, get_output_string
from runtime_tracing.taint_wrappers import get_taint_origins, taint_wrap


# ===========================================================
# Generic wrappers for caching and server notification
# ===========================================================


def notify_server_patch(fn):
    """
    Wrap `fn` to cache results and notify server of calls.

    - On cache hit, returns stored result immediately
    - On cache miss, invokes `fn` and stores result
    - Cache keys include function inputs and caller location
    - Sends call details to server for monitoring
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        # Get caller location
        frame = inspect.currentframe()
        caller = frame and frame.f_back
        file_name = caller.f_code.co_filename
        line_no = caller.f_lineno

        # Check cache first
        cached_out = CACHE.get_output(file_name, line_no, fn, args, kwargs)
        if cached_out is not None:
            result = cached_out
        else:
            result = fn(*args, **kwargs)
            CACHE.cache_output(result, file_name, line_no, fn, args, kwargs)

        # Notify server
        thread_id = threading.get_ident()
        try:
            task_id = id(asyncio.current_task())
        except RuntimeError:
            task_id = None

        message = {
            "type": "call",
            "file": file_name,
            "line": line_no,
            "thread": thread_id,
            "task": task_id,
        }
        try:
            send_to_server(message)
        except Exception:
            pass  # best-effort only

        return result

    return wrapper


def no_notify_patch(fn):
    """
    Wrap `fn` to cache results without server notification.

    - On cache hit, returns stored result immediately
    - On cache miss, invokes `fn` and stores result
    - Cache keys include function inputs and caller location
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        # Get caller location
        frame = inspect.currentframe()
        caller = frame and frame.f_back
        file_name = caller.f_code.co_filename
        line_no = caller.f_lineno

        # Check cache first
        cached_out = CACHE.get_output(file_name, line_no, fn, args, kwargs)
        if cached_out is not None:
            return cached_out

        # Run function and cache result
        result = fn(*args, **kwargs)
        CACHE.cache_output(result, file_name, line_no, fn, args, kwargs)
        return result

    return wrapper


def get_input_dict(func, *args, **kwargs):
    # Arguments are normalized to the function's parameter order.
    # func(a=5, b=2) and func(b=2, a=5) will result in same dict.
    sig = inspect.signature(func)
    try:
        bound = sig.bind(*args, **kwargs)
    except TypeError:
        # Many APIs only accept kwargs
        bound = sig.bind(**kwargs)
    bound.apply_defaults()
    input_dict = dict(bound.arguments)
    if "self" in input_dict:
        del input_dict["self"]
    return input_dict


def send_graph_node_and_edges(node_id, input_dict, output_obj, source_node_ids, api_type):
    """Send graph node and edge updates to the server."""
    # Get caller location TODO: Do we need this?
    frame = inspect.currentframe()
    caller = frame and frame.f_back
    file_name = caller.f_code.co_filename if caller else "unknown"
    line_no = caller.f_lineno if caller else 0
    codeLocation = f"{file_name}:{line_no}"

    # Get strings to display in UI.
    input_string, attachments = get_input(input_dict, api_type)
    output_string = get_output_string(output_obj, api_type)
    model = get_model_name(input_dict, api_type)

    # Send node
    logger.debug(f"Send add node {get_session_id()}")
    node_msg = {
        "type": "add_node",
        "session_id": get_session_id(),
        "node": {
            "id": node_id,
            "input": input_string,
            "output": output_string,
            "border_color": CERTAINTY_YELLOW,  # TODO: Set based on certainty.
            "label": model,  # TODO: Later label with LLM.
            "codeLocation": codeLocation,
            "model": model,
            "attachments": attachments,
        },
        "incoming_edges": source_node_ids,
    }

    # try:
    send_to_server(node_msg)
    # except Exception as e:
    #     logger.error(f"Failed to send add_node: {e}")
