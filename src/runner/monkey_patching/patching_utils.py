import asyncio
import inspect
import functools
import threading
import functools
from aco.runner.context_manager import get_session_id
from aco.common.constants import CERTAINTY_GREEN, CERTAINTY_RED, CERTAINTY_YELLOW
from aco.common.utils import send_to_server
from aco.server.cache_manager import CACHE
from aco.common.logger import logger
from aco.runner.monkey_patching.api_parser import get_input, get_model_name, get_output
from aco.runner.taint_wrappers import untaint_if_needed


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

    # Try to get signature, handling "invalid method signature" error
    sig = None
    try:
        sig = inspect.signature(func)
    except ValueError as e:
        if "invalid method signature" in str(e):
            # This can happen with monkey-patched bound methods
            # Try to get the signature from the unbound method instead
            if hasattr(func, "__self__") and hasattr(func, "__func__"):
                try:
                    # Get the unbound function from the class
                    cls = func.__self__.__class__
                    func_name = func.__name__
                    unbound_func = getattr(cls, func_name)
                    sig = inspect.signature(unbound_func)

                    # For unbound methods, we need to include 'self' in the arguments
                    # when binding, so prepend the bound object as the first argument
                    args = (func.__self__,) + args
                except (AttributeError, TypeError):
                    # If we can't get the unbound signature, re-raise the original error
                    raise e
        else:
            # Re-raise other ValueError exceptions
            raise e

    if sig is None:
        raise ValueError("Could not obtain function signature")

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
    frame = inspect.currentframe()
    user_program_frame = inspect.getouterframes(frame)[2]
    line_no = user_program_frame.lineno
    file_name = user_program_frame.filename
    codeLocation = f"{file_name}:{line_no}"

    # Get strings to display in UI.
    input_string, attachments, tools = get_input(input_dict, api_type)

    # Untaint the output object before processing to avoid Pydantic validation issues
    untainted_output_obj = untaint_if_needed(output_obj)
    output_string = get_output(untainted_output_obj, api_type)
    model = get_model_name(input_dict, api_type)

    # Send node
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

    try:
        send_to_server(node_msg)
    except Exception as e:
        logger.error(f"Failed to send add_node: {e}")
