import asyncio
import inspect
import json
import threading
import functools
from runtime_tracing.cache_manager import CACHE
from common.logging_config import setup_logging
logger = setup_logging()
from common.utils import extract_key_args
from runtime_tracing.taint_wrappers import taint_wrap, is_tainted, get_taint_origin, TaintedOpenAIResponse


# ===========================================================
# Generic wrappers.
# ===========================================================

def notify_server_patch(fn, server_conn):
    """
    Wrap `fn` so that:
      - On cache hit, the stored result is returned immediately.
      - On cache miss, `fn` is invoked and its result stored.

      - Cache keys are fn inputs and caller file and line_no.
      - The entries are tagged with caller file and line_no so the caller's 
        cache can be cleared.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        # 1. Figure out the caller's file and line_no.
        frame = inspect.currentframe()
        caller = frame and frame.f_back
        file_name = caller.f_code.co_filename
        line_no = caller.f_lineno

        # 2. Compute output.
        cached_out = CACHE.get_output(file_name, line_no, fn, args, kwargs)
        if cached_out is not None:
            result = cached_out
        else:
            result = fn(*args, **kwargs)
            CACHE.cache_output(result, file_name, line_no, fn, args, kwargs)

        # 3. Notify server.
        thread_id = threading.get_ident()
        try:
            task_id = id(asyncio.current_task())
        except RuntimeError:
            task_id = None

        message = {
            "type":   "call",
            "file":   file_name,
            "line":   line_no,
            "thread": thread_id,
            "task":   task_id,
        }
        try:
            server_conn.sendall((json.dumps(message) + "\n").encode("utf-8"))
        except Exception:
            pass  # best-effort only

        return result

    return wrapper


def no_notify_patch(fn):
    """
    Wrap `fn` so that:
      - On cache hit, the stored result is returned immediately.
      - On cache miss, `fn` is invoked and its result stored.

      - Cache keys are fn inputs and caller file and line_no.
      - The entries are tagged with caller file and line_no so the caller's 
        cache can be cleared.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        # 1. Figure out the caller's file and line_no.
        frame = inspect.currentframe()
        caller = frame and frame.f_back
        file_name = caller.f_code.co_filename
        line_no = caller.f_lineno

        # 2. Return cached output.
        cached_out = CACHE.get_output(file_name, line_no, fn, args, kwargs)
        if cached_out is not None:
            return cached_out
        
        # 3. Run function and cache result.
        result = fn(*args, **kwargs)
        CACHE.cache_output(result, file_name, line_no, fn, args, kwargs)
        return result
    
    return wrapper



# ===========================================================
# LLM API wrappers: Just replace string in request objects.
# ===========================================================

# TODO: Just make specific to the reponses etc for OpenAI etc so objects still the same, just text different.


def monkey_patch_llm_call(server_conn):
    """
    Monkey-patch agent_copilot.src.mock.call to intercept LLM calls.
    Sends call details (input, output, file, line, thread, task) to the server.
    """
    try:
        import agent_copilot.src.mock as ac_mock
    except ImportError:
        return  # If the module isn't available, do nothing
    original_call = getattr(ac_mock, "call", None)
    if original_call is None:
        return
    def patched_call(prompt: str) -> str:
        # Invoke the original LLM call (e.g., to get a response or raise an error)
        result = None
        error = None
        try:
            result = original_call(prompt)
        except Exception as e:
            error = e  # capture exception to report it, then re-raise
        # Gather call site info (filename and line number of the caller)
        frame = inspect.currentframe()
        caller = frame.f_back if frame else None
        file_name = caller.f_code.co_filename if caller else "<unknown>"
        line_no = caller.f_lineno if caller else -1
        # Identify thread and asyncio task
        thread_id = threading.get_ident()
        task_id = None
        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None
        if task:
            task_id = id(task)
        # Send the call details to the server
        message = {
            "type": "call",
            "input": prompt,
            "output": result if error is None else str(error),
            "file": file_name,
            "line": line_no,
            "thread": thread_id,
            "task": task_id
        }
        try:
            server_conn.sendall((json.dumps(message) + "\n").encode('utf-8'))
        except Exception:
            pass  # If sending fails (e.g., server down), skip
        if error:
            # Propagate the original exception after logging
            raise error
        return result
    ac_mock.call = patched_call


def _taint_and_log_openai_result(result, input_obj, file_name, line_no, from_cache, server_conn, any_input_tainted, input_taint):
    """
    Shared logic for tainting, warning, and sending server message for OpenAI LLM calls.
    """
    if any_input_tainted:
        print("[TAINT WARNING] OpenAI called with tainted input!")
    # Always wrap the output as a new, independent taint source
    result = TaintedOpenAIResponse(result)

    thread_id = threading.get_ident()
    try:
        task_id = id(asyncio.current_task())
    except Exception:
        task_id = None

    message = {
        "type": "call",
        "input": input_obj,
        "output": str(result),
        "file": file_name,
        "line": line_no,
        "thread": thread_id,
        "task": task_id,
        "from_cache": from_cache,
        "tainted": any_input_tainted,
        "taint_label": None,  # Output is always a new source
    }
    try:
        server_conn.sendall((json.dumps(message) + "\n").encode("utf-8"))
    except Exception:
        pass  # best-effort only
    return result


def v1_openai_patch(server_conn):
    """
    Patch openai.ChatCompletion.create (v1/classic API) to always taint the output as a new source.
    Warn if any input is tainted. Send call details to the server.
    """
    try:
        import openai
    except ImportError:
        return  # If openai isn't available, do nothing

    original_create = getattr(openai.ChatCompletion, "create", None)
    if original_create is None:
        return

    def patched_create(*args, **kwargs):
        frame = inspect.currentframe()
        caller = frame.f_back if frame else None
        file_name = caller.f_code.co_filename if caller else "<unknown>"
        line_no = caller.f_lineno if caller else -1

        cached_out = CACHE.get_output(file_name, line_no, original_create, args, kwargs)
        from_cache = cached_out is not None
        if from_cache:
            result = cached_out
        else:
            result = original_create(*args, **kwargs)
            CACHE.cache_output(result, file_name, line_no, original_create, args, kwargs)

        # Taint logic
        def check_taint(val):
            if is_tainted(val):
                return get_taint_origin(val)
            if isinstance(val, (list, tuple)):
                return [check_taint(v) for v in val]
            if isinstance(val, dict):
                return {k: check_taint(v) for k, v in val.items()}
            return None
        input_obj = kwargs.get("messages", args[0] if args else None)
        input_taint = check_taint(input_obj)
        any_input_tainted = input_taint is not None and input_taint != {} and input_taint != []
        return _taint_and_log_openai_result(result, input_obj, file_name, line_no, from_cache, server_conn, any_input_tainted, input_taint)

    openai.ChatCompletion.create = patched_create


def v2_openai_patch(server_conn):
    """
    Patch OpenAI().responses.create (v2/client API) to always taint the output as a new source.
    Warn if any input is tainted. Send call details to the server.
    """
    try:
        from openai import OpenAI
        from openai.resources.responses import Responses
    except ImportError:
        logger.warning("Could not import OpenAI or Responses for patching.")
        return

    original_init = OpenAI.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        original_create = self.responses.create
        def patched_create(*args, **kwargs):
            frame = inspect.currentframe()
            caller = frame.f_back if frame else None
            file_name = caller.f_code.co_filename if caller else "<unknown>"
            line_no = caller.f_lineno if caller else -1

            cache_key_args = extract_key_args(original_create, args, kwargs, ["model", "input"])
            model, input_text = cache_key_args

            cached_out = CACHE.get_output(file_name, line_no, original_create, cache_key_args, {})
            from_cache = cached_out is not None
            if from_cache:
                result = cached_out
            else:
                if len(args) == 1 and isinstance(args[0], Responses):
                    result = original_create(**kwargs)
                else:
                    result = original_create(*args, **kwargs)
                CACHE.cache_output(result, file_name, line_no, original_create, cache_key_args, {})

            # Taint logic
            def check_taint(val):
                if is_tainted(val):
                    return get_taint_origin(val)
                if isinstance(val, (list, tuple)):
                    return [check_taint(v) for v in val]
                if isinstance(val, dict):
                    return {k: check_taint(v) for k, v in val.items()}
                return None
            input_obj = kwargs.get("input", args[1] if len(args) > 1 else None)
            input_taint = check_taint(input_obj)
            any_input_tainted = input_taint is not None and input_taint != {} and input_taint != []
            return _taint_and_log_openai_result(result, input_obj, file_name, line_no, from_cache, server_conn, any_input_tainted, input_taint)
        self.responses.create = patched_create.__get__(self.responses, Responses)
    OpenAI.__init__ = new_init


# Update patch function list
CUSTOM_PATCH_FUNCTIONS = []
CUSTOM_PATCH_FUNCTIONS.append(v1_openai_patch)
CUSTOM_PATCH_FUNCTIONS.append(v2_openai_patch)
