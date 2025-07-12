import asyncio
import inspect
import json
import threading
import functools
import uuid
import logging
from workflow_edits.cache_manager import CACHE
from common.logging_config import setup_logging
from workflow_edits.utils import extract_output_text
logger = setup_logging()
from common.utils import extract_key_args
from runtime_tracing.taint_wrappers import check_taint, taint_wrap, get_origin_nodes
from openai.types.responses.response import Response


# ===========================================================
# Generic wrappers for caching and server notification
# ===========================================================

def notify_server_patch(fn, server_conn):
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
            server_conn.sendall((json.dumps(message) + "\n").encode("utf-8"))
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


# ===========================================================
# Session management
# ===========================================================

# Global session_id, set by set_session_id()
session_id = None

def set_session_id(sid):
    global session_id
    session_id = sid


# ===========================================================
# Graph tracking utilities
# ===========================================================

def _send_graph_node_and_edges(server_conn, node_id, input_obj, output, source_node_ids, model, api_type):
    """Send graph node and edge updates to the server."""
    # Send node
    node_msg = {
        "type": "addNode",
        "session_id": session_id,
        "node": {
            "id": node_id,
            "input": input_obj,
            "output": extract_output_text(output, api_type),
            "border_color": "#00c542",
            "label": "Label",
            "model": model,
            "api_type": api_type,
        }
    }
    try:
        server_conn.sendall((json.dumps(node_msg) + "\n").encode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to send addNode: {e}")

    # Send edges for each source
    for src in source_node_ids:
        if src != node_id:
            edge_msg = {
                "type": "addEdge",
                "session_id": session_id,
                "edge": {"source": src, "target": node_id}
            }
            try:
                server_conn.sendall((json.dumps(edge_msg) + "\n").encode("utf-8"))
            except Exception as e:
                logger.warning(f"Failed to send addEdge: {e}")


def _extract_source_node_ids(taint):
    """Extract source node IDs from taint structure."""
    if isinstance(taint, list):
        # New taint structure: list of node IDs directly
        return [str(node_id) for node_id in taint if node_id is not None]
    if isinstance(taint, dict):
        # Check for new taint structure with origin_nodes
        if 'origin_nodes' in taint:
            return [str(node_id) for node_id in taint['origin_nodes'] if node_id is not None]
        # Check for old taint structure with node_id
        if 'node_id' in taint:
            return [str(taint['node_id'])]
        # Recursively check nested dicts
        ids = []
        for v in taint.values():
            ids.extend(_extract_source_node_ids(v))
        return ids
    if isinstance(taint, str):
        # Single node ID as string
        return [taint] if taint else []
    return []


def _taint_and_log_openai_result(result, file_name, line_no, from_cache, server_conn, any_input_tainted, input_taint, model, api_type, cached_node_id=None, input_to_use=None):
    """
    Shared logic for tainting, logging, and sending server messages for OpenAI LLM calls.
    Also constructs and sends LLM call graph updates.

    TODO: Refactor. This does too much. Also should be more general than OAI.
    """
    print("in taint")
    # Use cached node ID if available, otherwise generate new one
    node_id = cached_node_id if cached_node_id else str(uuid.uuid4())
    
    # Extract source node IDs from input taint
    source_node_ids = _extract_source_node_ids(input_taint)
    
    if any_input_tainted:
        logger.warning("OpenAI called with tainted input!")
    
    # Wrap output as new taint source
    result = taint_wrap(result, {'origin_nodes': [node_id]})

    # Get thread and task info
    thread_id = threading.get_ident()
    try:
        task_id = id(asyncio.current_task())
    except Exception:
        task_id = None

    # Send call message to server (now includes model and node_id)
    message = {
        "type": "call",
        "input": input_to_use,
        "output": extract_output_text(result, api_type),
        "model": model,
        "file": file_name,
        "line": line_no,
        "thread": thread_id,
        "task": task_id,
        "from_cache": from_cache,
        "tainted": any_input_tainted,
        "taint_label": {'node_id': node_id, 'origin': f'{file_name}:{line_no}'},
        "node_id": node_id,
        "api_type": api_type,
    }
    try:
        server_conn.sendall((json.dumps(message) + "\n").encode("utf-8"))
        print("Sent")
    except Exception as e:
        print("Exception", e)
        pass  # best-effort only

    # Send graph updates (addNode/addEdge) with model
    _send_graph_node_and_edges(server_conn, node_id, input_to_use, result, source_node_ids, model, api_type)

    return result


# ===========================================================
# OpenAI API patches
# ===========================================================

def v1_openai_patch(server_conn):
    """
    Patch openai.ChatCompletion.create (v1/classic API) to use persistent cache and edits.
    """
    try:
        import openai
    except ImportError:
        return  # If openai isn't available, do nothing

    original_create = getattr(openai.ChatCompletion, "create", None)
    if original_create is None:
        return

    def patched_create(*args, **kwargs):
        # Extract model and messages
        model = kwargs.get("model", args[0] if args else None)
        messages = kwargs.get("messages", args[1] if len(args) > 1 else None)
        # Use get_raw if present
        if hasattr(model, 'get_raw'):
            model = model.get_raw()
        if hasattr(messages, 'get_raw'):
            messages = messages.get_raw()
        # Use persistent cache/edits
        input_to_use, output_to_use, cached_node_id = CACHE.get_in_out(session_id, model, str(messages))
        from_cache = output_to_use is not None
        new_node_id = None
        if output_to_use is not None:
            result = output_to_use
        else:
            # Call real LLM with possibly edited input
            result = original_create(model=model, messages=messages) if input_to_use is None else original_create(model=model, messages=input_to_use)
            # Generate node ID for new result
            new_node_id = str(uuid.uuid4())
            CACHE.cache_output(session_id, model, str(messages if input_to_use is None else input_to_use), result, 'openai_v1', new_node_id)
        # Taint/graph logic
        def check_taint(val):
            if get_origin_nodes(val):
                return get_origin_nodes(val)
            if isinstance(val, (list, tuple)):
                return [check_taint(v) for v in val]
            if isinstance(val, dict):
                return {k: check_taint(v) for k, v in val.items()}
            return None
        input_obj = messages
        input_taint = check_taint(input_obj)
        any_input_tainted = input_taint is not None and input_taint != {} and input_taint != []
        # Use new_node_id for new results, cached_node_id for cached results
        node_id_to_use = new_node_id if not from_cache else cached_node_id
        return _taint_and_log_openai_result(result, input_obj, '<cache>', 0, from_cache, server_conn, any_input_tainted, input_taint, model, 'openai_v1', node_id_to_use, input_to_use=input_to_use)

    openai.ChatCompletion.create = patched_create


def response_to_json(response: Response) -> str:
    """Serialize a Response object to a JSON string for storage."""
    return json.dumps(response.model_dump())

def json_to_response(json_str: str) -> Response:
    """Deserialize a JSON string from the DB to a Response object."""
    data = json.loads(json_str)
    return Response(**data)

def inject_output_text(response_dict: dict, new_text: str) -> dict:
    """Inject new_text into the correct place in the response dict."""
    try:
        response_dict["output"][0]["content"][0]["text"] = new_text
    except Exception as e:
        raise ValueError(f"Failed to inject output text: {e}")
    return response_dict


def v2_openai_patch(server_conn):
    """
    Patch OpenAI().responses.create (v2/client API) to use persistent cache and edits.
    """
    from openai import OpenAI
    from openai.resources.responses import Responses

    # TODO: I think openai.responses is at attirbute of the Openai object (client).
    # So we need to patch openai.responses. create for every instance and cannot do it globally. 
    # I need to verify this!
    original_init = OpenAI.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        original_create = self.responses.create

        def patched_create(*args, **kwargs):
            print("="*20)
            # Get model and input_text.
            model = kwargs.get("model", args[0] if args else None)
            input = kwargs.get("input", args[1] if len(args) > 1 else None)
            
            # Get raw values if input is wrapped.
            print("INPUT TYPE", type(input))
            if hasattr(model, 'get_raw'):
                model = model.get_raw()
                print("MODEL IS OBJECT")
            if hasattr(input, 'get_raw'):
                input_text = input.get_raw()
                print("INPUT IS OBJECT")
            else:
                input_text = input

            # Check if there's a cached / edited input/output.
            input_to_use, output_to_use, cached_node_id = CACHE.get_in_out(session_id, model, str(input_text))
            from_cache = output_to_use is not None
            new_node_id = None

            # Produce output.
            if output_to_use is not None:
                # Use cached output.
                print("Using cached response")
                result = json_to_response(output_to_use)
                # For cached results, we need to preserve the original taint structure
                # The result should already be taint-wrapped from the original call
                # We don't re-wrap it here to avoid creating new node IDs
            
            else:
                # Call LLM.
                new_kwargs = dict(kwargs)
                new_kwargs["input"] = input_to_use
                # TODO: Test below, is this really the way to go?
                if len(args) == 1 and isinstance(args[0], Responses):
                    result = original_create(**new_kwargs)
                else:
                    result = original_create(*args, **new_kwargs)

                print("[DEBUG] After LLM call, before taint_wrap:")
                print("  type:", type(result))
                # print("  repr:", repr(result))
                
                # Generate node ID for new result
                new_node_id = str(uuid.uuid4())
                # Cache.
                CACHE.cache_output(session_id, model, str(input_to_use), result, 'openai_v2', new_node_id)
                result = taint_wrap(result, {'origin_nodes': [new_node_id]})
                print("[DEBUG] After taint_wrap:")
                print("  type:", type(result))
                # print("  repr:", repr(result))
                print("  get_origin_nodes:", get_origin_nodes(result))

            # TODO: The check for taint should be in the log openai result.
            # I think input text is "untainted."
            # input_obj = input_text
            input_taint = check_taint(input)
            any_input_tainted = input_taint is not None and input_taint != {} and input_taint != []
            print("any input tainted:", any_input_tainted)
            # TODO: Refactor taint_and_log_openai_result -- too much at once.
            # TODO: Remove the None defaults in that function.
            # Use new_node_id for new results, cached_node_id for cached results
            node_id_to_use = new_node_id if not from_cache else cached_node_id
            return _taint_and_log_openai_result(result=result, 
                                                file_name="filename.py", 
                                                line_no=-1,
                                                from_cache=from_cache, 
                                                server_conn=server_conn,
                                                any_input_tainted=any_input_tainted,
                                                input_taint=input_taint,
                                                model=model,
                                                api_type='openai_v2',
                                                cached_node_id=node_id_to_use,
                                                input_to_use=input_to_use)
        
        self.responses.create = patched_create.__get__(self.responses, Responses)
    OpenAI.__init__ = new_init


# ===========================================================
# Patch function registry
# ===========================================================

CUSTOM_PATCH_FUNCTIONS = [
    v1_openai_patch,
    v2_openai_patch,
]
