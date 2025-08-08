import asyncio
import inspect
import json
import threading
import functools
from io import BytesIO
from workflow_edits.cache_manager import CACHE
from common.logger import logger
from workflow_edits.utils import extract_output_text, json_to_response
from runtime_tracing.taint_wrappers import get_taint_origins, taint_wrap
from openai import OpenAI
from openai.resources.responses import Responses
import openai


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

def _send_graph_node_and_edges(server_conn, 
                               node_id, 
                               input, 
                               output_obj, 
                               source_node_ids, 
                               model, 
                               api_type,
                               attachements=[]):
    """Send graph node and edge updates to the server."""
    # Get caller location
    frame = inspect.currentframe()
    caller = frame and frame.f_back
    file_name = caller.f_code.co_filename if caller else "unknown"
    line_no = caller.f_lineno if caller else 0
    codeLocation = f"{file_name}:{line_no}"

    # Send node
    node_msg = {
        "type": "add_node",
        "session_id": session_id,
        "node": {
            "id": node_id,
            "input": input,
            "output": extract_output_text(output_obj, api_type),
            "border_color": "#00c542", # TODO: Set based on certainty.
            "label": f"{model}", # TODO: Later label with LLM.
            "codeLocation": codeLocation,
            "model": model,
            "attachments": attachements,
        }
    }

    try:
        server_conn.sendall((json.dumps(node_msg) + "\n").encode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to send add_node: {e}")

    # Send edges for each source
    for src in source_node_ids:
        if src != node_id:
            edge_msg = {
                "type": "add_edge",
                "session_id": session_id,
                "edge": {"source": src, "target": node_id}
            }
            try:
                server_conn.sendall((json.dumps(edge_msg) + "\n").encode("utf-8"))
            except Exception as e:
                logger.error(f"Failed to send addEdge: {e}")


# ===========================================================
# OpenAI API patches
# ===========================================================

def v2_openai_patch(server_conn):
    original_init = OpenAI.__init__
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        patch_openai_responses_create(self.responses, server_conn)
        patch_openai_beta_assistants_create(self.beta.assistants)
        patch_openai_beta_threads_create(self.beta.threads)
        patch_openai_beta_threads_runs_create_and_poll(self.beta.threads.runs, server_conn)
        patch_openai_files_create(self.files)
    OpenAI.__init__ = new_init

def v1_openai_patch(server_conn):
    """
    Patch openai.ChatCompletion.create (v1/classic API) to use persistent cache and edits.
    """
    # raise NotImplementedError
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
        input_to_use, output_to_use, node_id = CACHE.get_in_out(session_id, model, str(messages))

        # Taint origins: combine from input and model
        taint_origins = get_taint_origins(messages) + get_taint_origins(model)

        # Produce output
        if output_to_use is not None:
            # Use cached output (assume already in correct format)
            result = output_to_use
        else:
            # Call LLM with possibly edited input
            call_kwargs = dict(kwargs)
            call_kwargs["model"] = model
            call_kwargs["messages"] = input_to_use
            result = original_create(**call_kwargs)
            # Cache
            CACHE.cache_output(session_id, node_id, result, "openai_v1")

        # Send to server (graph node/edges)
        _send_graph_node_and_edges(
            server_conn=server_conn,
            node_id=node_id,
            input=input_to_use,
            output_obj=result,
            source_node_ids=taint_origins,
            model=model,
            api_type="openai_v1"
        )

        # Wrap and return
        return taint_wrap(result, [node_id])

    openai.ChatCompletion.create = patched_create

def patch_openai_responses_create(responses, server_conn):
    original_create = responses.create
    def patched_create(*args, **kwargs):
        model = kwargs.get("model", args[0] if args else [])
        input = kwargs.get("input", args[1] if len(args) > 1 else [])
        taint_origins = get_taint_origins(input) + get_taint_origins(model)
        # Check if there's a cached / edited input/output
        input_to_use, output_to_use, node_id = CACHE.get_in_out(session_id, model, input)
        if output_to_use is not None:
            result = json_to_response(output_to_use, "openai_v2_response")
        else:
            new_kwargs = dict(kwargs)
            new_kwargs["input"] = input_to_use
            assert len(args) == 1 and isinstance(args[0], Responses) # OpenAI: all args must be kwargs
            result = original_create(**new_kwargs)
            CACHE.cache_output(session_id, node_id, result, "openai_v2_response")
        _send_graph_node_and_edges(server_conn=server_conn,
                                   node_id=node_id,
                                   input=input_to_use,
                                   output_obj=result,
                                   source_node_ids=taint_origins,
                                   model=model,
                                   api_type="openai_v2_response")
        return taint_wrap(result, [node_id])
    responses.create = patched_create.__get__(responses, Responses)

def patch_openai_beta_threads_runs_create_and_poll(runs, server_conn):
    original_create_and_poll = runs.create_and_poll
    def patched_create_and_poll(self, **kwargs):
        client = self._client

        # Get inputs (most recent user message). 
        attachments_list = []
        thread_id = kwargs.get("thread_id")
        input_content = None

        try:
            input = client.beta.threads.messages.list(thread_id=thread_id).data[0]
            if input.content:
                input_content = input.content[0].text.value
            if hasattr(input, "attachments") and input.attachments:
                for att in input.attachments:
                    file_id = att.file_id
                    if file_id:
                        # Get file metadata for filename
                        file_info = client.files.retrieve(file_id)
                        file_name = file_info.filename
                        # Get file path from cache
                        file_path = CACHE.get_file_path(file_id)
                        attachments_list.append((file_name, file_path))
        except IndexError:
            logger.error("No user message.") # TODO: How to handle this? What does OAI do?

        # Get taint origins.
        taint_origins = get_taint_origins(kwargs)

        # Get the model.
        assistant_id = kwargs.get("assistant_id")
        model = "unknown"
        if assistant_id:
            assistant = client.beta.assistants.retrieve(assistant_id)
            model = getattr(assistant, "model", None)

        # Call original create_and_poll method.
        # NOTE: Caching the output is not easy here ... probably can't support it.
        _, _, node_id = CACHE.get_in_out(session_id, model, input_content)
        result = original_create_and_poll(**kwargs)

        # Get most recent message (LLM response).
        output_obj = None
        try:
            output_obj = client.beta.threads.messages.list(thread_id=thread_id).data[0]
        except IndexError:
            logger.error("No most recent message (LLM response).") # TODO: How to handle. What does OAI do?

        _send_graph_node_and_edges(
            server_conn=server_conn,
            node_id=node_id,
            input=input_content,
            output_obj=output_obj,
            source_node_ids=taint_origins,
            model=model,
            api_type="openai_assistant_query",
            attachements=attachments_list,
        )
        return taint_wrap(result, [node_id])
    runs.create_and_poll = patched_create_and_poll.__get__(runs, type(original_create_and_poll))

def patch_openai_beta_assistants_create(assistants_instance):
    """
    Patch the .create method of an OpenAI beta assistants instance to propagate taint origins from any input argument to the result.
    If no input is tainted, propagate an empty origin list.
    """
    original_create = assistants_instance.create

    def patched_create(*args, **kwargs):
        # Collect taint origins from all args and kwargs
        taint_origins = set()
        for arg in args:
            taint_origins.update(get_taint_origins(arg))
        for val in kwargs.values():
            taint_origins.update(get_taint_origins(val))
        # Call the original method
        result = original_create(*args, **kwargs)
        # Propagate taint
        return taint_wrap(result, list(taint_origins))

    assistants_instance.create = patched_create


def patch_openai_beta_threads_create(threads_instance):
    """
    Patch the .create method of an OpenAI beta threads instance to propagate taint origins and support input editing.
    """
    original_create = threads_instance.create

    def patched_create(*args, **kwargs):        
        # Get the content from the last message in the messages list
        # TODO: Should we handle empty messages list? What does OAI do there?
        messages = kwargs.get("messages", [])
        last_message = messages[-1]
        input_content = last_message.get("content", "")
        
        # Get taint origins from all args and kwargs, including the input content
        taint_origins = get_taint_origins(args) + get_taint_origins(kwargs) + get_taint_origins(input_content)
        
        # Check if there's a cached input
        input_to_use, _, _ = CACHE.get_in_out(session_id, None, input_content)
        # If input is overwritten, update the last message content
        new_messages = messages.copy()
        new_messages[-1] = {**new_messages[-1], "content": input_to_use}
        new_kwargs = dict(kwargs)
        new_kwargs["messages"] = new_messages
        result = original_create(*args, **new_kwargs)

        # Forward taint: if input is tainted, output should be tainted with the same taint origins
        return taint_wrap(result, taint_origins)

    threads_instance.create = patched_create


def patch_openai_files_create(files_resource):
    original_create = files_resource.create

    def patched_create(self, **kwargs):
        # Extract file argument
        file_arg = kwargs.get("file")
        if isinstance(file_arg, tuple) and len(file_arg) >= 2:
            file_name = file_arg[0]
            fileobj = file_arg[1]
        elif hasattr(file_arg, "read"):
            fileobj = file_arg
            file_name = getattr(fileobj, "name", "unknown")
        else:
            raise ValueError("The 'file' argument must be a tuple (filename, fileobj, content_type) or a file-like object.")
        
        # Create a copy of the file content before the original API call consumes it
        fileobj.seek(0)
        file_content = fileobj.read()
        fileobj.seek(0)
        
        # Create a BytesIO object with the content for our cache functions
        fileobj_copy = BytesIO(file_content)
        fileobj_copy.name = getattr(fileobj, "name", "unknown")
        
        # Call the original method
        result = original_create(**kwargs)
        # Get file_id from result
        file_id = getattr(result, "id", None)
        if file_id is None:
            raise ValueError("OpenAI did not return a file id after file upload.")
        CACHE.cache_file(file_id, file_name, fileobj_copy)
        # Propagate taint from fileobj if present
        taint_origins = get_taint_origins(fileobj)
        return taint_wrap(result, taint_origins)
    files_resource.create = patched_create.__get__(files_resource, type(original_create))


# ===========================================================
# Anthropic API patches
# ===========================================================

def anthropic_patch(server_conn):
    """
    Patch Anthropic API to use persistent cache and edits.
    """
    try:
        import anthropic
    except ImportError:
        logger.info("Anthropic not installed, skipping Anthropic patches")
        return
    
    original_init = anthropic.Anthropic.__init__
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        patch_anthropic_messages_create(self.messages, server_conn)
        patch_anthropic_files_upload(self.beta.files, server_conn)
        patch_anthropic_files_list(self.beta.files)
        patch_anthropic_files_retrieve_metadata(self.beta.files)
        patch_anthropic_files_delete(self.beta.files)
    anthropic.Anthropic.__init__ = new_init

def patch_anthropic_messages_create(messages_instance, server_conn):
    """
    Patch the .create method of an Anthropic messages instance to handle caching and edits.
    """
    original_create = messages_instance.create
    
    def patched_create(*args, **kwargs):
        # Extract input from messages
        messages = kwargs.get("messages", [])
        model = kwargs.get("model", "unknown")
        
        # Get the last user message content
        input_content = None
        attachments_list = []
        
        if messages:
            last_message = messages[-1]
            content = last_message.get("content", "")
            
            if isinstance(content, str):
                input_content = content
            elif isinstance(content, list):
                # Handle multi-modal content
                text_parts = []
                for item in content:
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "document":
                        # Handle document attachments - create file path entry
                        source = item.get("source", {})
                        if source.get("type") == "base64":
                            # For now, we'll indicate this as a base64 document
                            attachments_list.append(("document.pdf", "base64_embedded"))
                input_content = " ".join(text_parts) if text_parts else str(content)
        
        if input_content is None:
            input_content = str(kwargs)
        
        # Get taint origins from all inputs
        taint_origins = get_taint_origins(args) + get_taint_origins(kwargs)
        
        # Check cache and handle input/output overrides
        input_to_use, output_to_use, node_id = CACHE.get_in_out(session_id, model, input_content)
        
        if output_to_use is not None:
            result = json_to_response(output_to_use, "anthropic_messages")
        else:
            # Update messages with potentially edited input
            new_messages = messages.copy()
            if new_messages and input_to_use != input_content:
                last_message = new_messages[-1].copy()
                original_content = last_message.get("content", "")
                
                # Handle multimodal content preservation
                if isinstance(original_content, list):
                    # Preserve document attachments, update only text content
                    new_content = []
                    for item in original_content:
                        if item.get("type") == "text":
                            # Update text content with edited input
                            new_content.append({
                                "type": "text", 
                                "text": input_to_use
                            })
                        else:
                            # Preserve non-text content (documents, etc.)
                            new_content.append(item)
                    last_message["content"] = new_content
                else:
                    # Simple text content
                    last_message["content"] = input_to_use
                
                new_messages[-1] = last_message
            
            new_kwargs = dict(kwargs)
            new_kwargs["messages"] = new_messages
            
            result = original_create(*args, **new_kwargs)
            CACHE.cache_output(session_id, node_id, result, "anthropic_messages", model)
        
        # Send to server (graph node/edges)
        _send_graph_node_and_edges(
            server_conn=server_conn,
            node_id=node_id,
            input=input_to_use,
            output_obj=result,
            source_node_ids=taint_origins,
            model=model,
            api_type="anthropic_messages",
            attachements=attachments_list
        )
        
        return taint_wrap(result, [node_id])
    
    messages_instance.create = patched_create

def patch_anthropic_files_upload(files_instance, server_conn):
    """
    Patch the .upload method of an Anthropic files instance to handle file caching.
    """
    original_upload = files_instance.upload
    
    def patched_upload(*args, **kwargs):
        # Extract file argument
        file_arg = kwargs.get("file")
        file_name = "unknown"
        
        if hasattr(file_arg, "name"):
            file_name = file_arg.name
        elif hasattr(file_arg, "read"):
            file_name = getattr(file_arg, "name", "uploaded_file")
        
        # Call original method
        result = original_upload(*args, **kwargs)
        
        # Cache the file if we have caching enabled
        file_id = getattr(result, "id", None)
        if file_id and file_arg:
            CACHE.cache_file(file_id, file_name, file_arg)
        
        # Propagate taint from file input
        taint_origins = get_taint_origins(file_arg)
        return taint_wrap(result, taint_origins)
    
    files_instance.upload = patched_upload

def patch_anthropic_files_list(files_instance):
    """
    Patch the .list method of an Anthropic files instance to handle taint propagation.
    """
    original_list = files_instance.list
    
    def patched_list(*args, **kwargs):
        # Call original method
        result = original_list(*args, **kwargs)
        
        # Propagate taint from any input arguments
        taint_origins = get_taint_origins(args) + get_taint_origins(kwargs)
        return taint_wrap(result, taint_origins)
    
    files_instance.list = patched_list

def patch_anthropic_files_retrieve_metadata(files_instance):
    """
    Patch the .retrieve_metadata method of an Anthropic files instance to handle taint propagation.
    """
    original_retrieve_metadata = files_instance.retrieve_metadata
    
    def patched_retrieve_metadata(*args, **kwargs):
        # Call original method
        result = original_retrieve_metadata(*args, **kwargs)
        
        # Propagate taint from any input arguments
        taint_origins = get_taint_origins(args) + get_taint_origins(kwargs)
        return taint_wrap(result, taint_origins)
    
    files_instance.retrieve_metadata = patched_retrieve_metadata

def patch_anthropic_files_delete(files_instance):
    """
    Patch the .delete method of an Anthropic files instance to handle taint propagation.
    """
    original_delete = files_instance.delete
    
    def patched_delete(*args, **kwargs):
        # Call original method
        result = original_delete(*args, **kwargs)
        
        # Propagate taint from any input arguments
        taint_origins = get_taint_origins(args) + get_taint_origins(kwargs)
        return taint_wrap(result, taint_origins)
    
    files_instance.delete = patched_delete

# ===========================================================
# Patch function registry
# ===========================================================

# Only include patch functions that can be called at global patch time (with server_conn as argument).
# Subclient patching must be done inside the OpenAI.__init__ patch (see v2_openai_patch).
CUSTOM_PATCH_FUNCTIONS = [
    v1_openai_patch, # TODO: Doesn't work currently.
    v2_openai_patch,
    anthropic_patch,
]

# Subclient patch functions (e.g., patch_openai_responses_create, patch_openai_beta_threads_runs_create_and_poll)
# are NOT included here and should only be called from within the OpenAI.__init__ patch.