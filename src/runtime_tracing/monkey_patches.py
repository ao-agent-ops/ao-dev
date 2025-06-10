import asyncio
import inspect
import json
import threading
import functools
import importlib


"""
TODO: These outputs will make that any call to that function returns the same output. 
We need to get a cache key and check if it's there instead of just taking `output`. 
"""

# ===========================================================
# Generic wrappers.
# ===========================================================
def no_notify_patch(fn, *, input=None, output=None):
    """
    Wrap `fn` so that:

    - If `input` is not None, use that as the positional call arguments.
      * If `input` is a tuple, it's treated as (*args, **kwargs) tuple:
          ( (arg1, arg2, ...), {'kw': 'val', ...} )
      * If it's a dict, it's treated as kwargs.
      * Otherwise, it's a single positional argument.
    - If `output` is not None, skip calling `fn` and immediately return `output`.
    """
    @functools.wraps(fn)
    def wrapper(*orig_args, **orig_kwargs):
        # figure out args/kwargs override
        if input is not None:
            if isinstance(input, tuple) and len(input) == 2 and isinstance(input[1], dict):
                args, kwargs = input
            elif isinstance(input, dict):
                args, kwargs = (), input
            else:
                args, kwargs = (input,), {}
        else:
            args, kwargs = orig_args, orig_kwargs

        # if output override, return it directly
        if output is not None:
            return output

        # otherwise call the original
        return fn(*args, **kwargs)

    return wrapper


def notify_server_patch(fn, server_conn, *, input=None, output=None):
    """
    Wrap `fn` so that:
      - If `input` is not None, calls use that instead of the caller’s args.
      - If `output` is not None, skips `fn` and returns `output`.
      - Always sends a JSON message {"type":"call",…} over `server_conn`.
    """
    @functools.wraps(fn)
    def wrapper(*orig_args, **orig_kwargs):
        # 1. Figure out what to call (or skip)
        if input is not None:
            # allow (args, kwargs) tuple, plain dict, or single arg
            if isinstance(input, tuple) and len(input) == 2 and isinstance(input[1], dict):
                args, kwargs = input
            elif isinstance(input, dict):
                args, kwargs = (), input
            else:
                args, kwargs = (input,), {}
        else:
            args, kwargs = orig_args, orig_kwargs

        # 2. Invoke original (unless output override)
        result = None
        error = None
        if output is not None:
            result = output
        else:
            try:
                result = fn(*args, **kwargs)
            except Exception as e:
                error = e

        # 3. Gather call‐site metadata
        frame = inspect.currentframe()
        caller = frame.f_back if frame else None
        file_name = caller.f_code.co_filename if caller else "<unknown>"
        line_no   = caller.f_lineno if caller else -1
        thread_id = threading.get_ident()
        try:
            task = asyncio.current_task()
            task_id = id(task) if task else None
        except RuntimeError:
            task_id = None

        # 4. Send notification
        message = {
            "type":   "call",
            "input":  args if output is None else args,
            "output": result if error is None else str(error),
            "file":   file_name,
            "line":   line_no,
            "thread": thread_id,
            "task":   task_id
        }
        try:
            server_conn.sendall((json.dumps(message) + "\n").encode("utf-8"))
        except Exception:
            pass  # best‐effort only

        # 5. Propagate error or return
        if error:
            raise error
        return result

    return wrapper


# ===========================================================
# LLM API wrappers.
# ===========================================================

# TODO: Just make specific to the reponses etc for OpenAI etc so objects still the same, just text different.



# ===========================================================
# Utils to apply the wrappers.
# ===========================================================
# def patch_by_path(dotted_path, *, input=None, output=None, notify=False, server_conn=None):
#     """
#     Import the module+attr from `dotted_path`, wrap it with no_notify_patch,
#     and re-assign it in-place. Returns the original function.
#     """
#     module_path, attr = dotted_path.rsplit(".", 1)
#     module = importlib.import_module(module_path)
#     original = getattr(module, attr)
#     if notify:
#         assert server_conn is not None
#         wrapped = notify_server_patch(original, server_conn, input=input, output=output)
#     else:
#         wrapped = no_notify_patch(original, input=input, output=output)
#     setattr(module, attr, wrapped)
#     return original








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
