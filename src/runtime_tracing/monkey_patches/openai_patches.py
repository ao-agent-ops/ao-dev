import asyncio
import inspect
import functools
import json
import threading
import functools
from io import BytesIO
from runtime_tracing.utils import get_input_dict, send_graph_node_and_edges
from agent_copilot.context_manager import get_session_id
from workflow_edits.cache_manager import CACHE
from common.logger import logger
from workflow_edits.utils import (
    get_cachable_input_openai_beta_threads_create,
    get_input,
    get_model_name,
    get_output_string,
)
from runtime_tracing.taint_wrappers import get_taint_origins, taint_wrap


# ===========================================================
# OpenAI API patches
# ===========================================================


def v2_openai_patch():
    try:
        from openai import OpenAI, AsyncOpenAI
    except ImportError:
        logger.info("OpenAI not installed, skipping OpenAI v2 patches")
        return

    def create_patched_init(original_init):
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            patch_openai_responses_create(self.responses)
            patch_openai_chat_completions_create(self.chat.completions)
            patch_openai_beta_assistants_create(self.beta.assistants)
            patch_openai_beta_threads_create(self.beta.threads)
            patch_openai_beta_threads_runs_create_and_poll(self.beta.threads.runs)
            patch_openai_files_create(self.files)

        return patched_init

    OpenAI.__init__ = create_patched_init(OpenAI.__init__)
    AsyncOpenAI.__init__ = create_patched_init(AsyncOpenAI.__init__)


# Patch for OpenAI.responses.create is called patch_openai_responses_create
def patch_openai_responses_create(responses):
    # Maybe the user doesn't have OpenAI installed.
    try:
        from openai import AsyncOpenAI
        from openai.resources.responses import AsyncResponses
        from openai.resources.responses import Responses
    except ImportError:
        return

    asynchronous = responses._client.__class__ == AsyncOpenAI
    ResponsesClass = Responses
    if asynchronous:
        ResponsesClass = AsyncResponses

    # Original OpenAI.responses.create function.
    original_function = responses.create

    if asynchronous:

        async def patched_function(*args, **kwargs):
            model = kwargs.get("model", args[0] if args else [])
            input = kwargs.get("input", args[1] if len(args) > 1 else [])
            taint_origins = get_taint_origins(input) + get_taint_origins(model)

            input_to_use, output_to_use, node_id = CACHE.get_in_out(get_session_id(), model, input)
            if output_to_use is not None:
                result = json_to_response(output_to_use, "AsyncOpenAI.responses.create")
            else:
                new_kwargs = dict(kwargs)
                new_kwargs["input"] = input_to_use
                result = await original_function(**new_kwargs)
                CACHE.cache_output(
                    get_session_id(), node_id, result, "AsyncOpenAI.responses.create"
                )

            send_graph_node_and_edges(
                node_id=node_id,
                input_dict=input_to_use,
                output_obj=result,
                source_node_ids=taint_origins,
                model=model,
                api_type="OpenAI.responses.create",
            )
            return taint_wrap(result, [node_id])

    else:
        # Patched function (executed instead of OpenAI.responses.create)
        def patched_function(*args, **kwargs):
            # 1. Set API identifier to fully qualified name of patched function.
            api_type = "OpenAI.responses.create"

            # 2. Get full input dict.
            input_dict = get_input_dict(original_function, *args, **kwargs)

            # 3. Get taint origins (did another LLM produce the input?).
            taint_origins = get_taint_origins(input_dict)

            # 4. Get result from cache or call LLM.
            input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
            if result is None:
                result = original_function(**input_to_use)  # Call LLM.
                CACHE.cache_output(node_id, result)

            # 5. Tell server that this LLM call happened.
            send_graph_node_and_edges(
                node_id=node_id,
                input_dict=input_to_use,
                output_obj=result,
                source_node_ids=taint_origins,
                api_type=api_type,
            )

            # 6. Taint the output object and return it.
            return taint_wrap(result, [node_id])

    responses.create = patched_function.__get__(responses, ResponsesClass)


def patch_openai_chat_completions_create(completions):
    try:
        from typing import Iterable
        from openai import AsyncOpenAI
        from openai.resources.completions import AsyncCompletions, Completions
        from openai.types.chat import ChatCompletionMessageParam
    except ImportError:
        return

    completions: Completions | AsyncCompletions
    asynchronous = completions._client.__class__ == AsyncOpenAI
    CompletionsClass = Completions
    if asynchronous:
        CompletionsClass = AsyncCompletions

    original_create = completions.create

    if asynchronous:

        async def patched_create(*args, **kwargs):
            """The shared logic"""
            model = kwargs.get("model", args[0] if args else [])
            input = kwargs.get("messages", args[1] if len(args) > 1 else [])

            input: Iterable[ChatCompletionMessageParam]
            # NOTE: This type is an iterable over a struct that has three fields: "content", "role", Optional: "name"
            # "name" is an optional name for the participant.

            taint_origins = get_taint_origins(input) + get_taint_origins(model)

            input_to_use, output_to_use, node_id = CACHE.get_in_out(get_session_id(), model, input)
            if output_to_use is not None:
                result = json_to_response(output_to_use, "OpenAI.responses.create")
            else:
                new_kwargs = dict(kwargs)
                new_kwargs["messages"] = input_to_use
                result = await original_create(**new_kwargs)  # This might be a coroutine
                CACHE.cache_output(get_session_id(), node_id, result, "OpenAI.responses.create")

            send_graph_node_and_edges(
                node_id=node_id,
                input_dict=str(input_to_use),
                output_obj=result,
                source_node_ids=taint_origins,
                model=model,
                api_type="OpenAI.responses.create",
            )
            return taint_wrap(result, [node_id])

    else:

        def patched_create(*args, **kwargs):
            """The shared logic"""
            model = kwargs.get("model", args[0] if args else [])
            input = kwargs.get("messages", args[1] if len(args) > 1 else [])

            input: Iterable[ChatCompletionMessageParam]
            # NOTE: This type is an iterable over a struct that has three fields: "content", "role", Optional: "name"
            # "name" is an optional name for the participant.

            taint_origins = get_taint_origins(input) + get_taint_origins(model)

            input_to_use, output_to_use, node_id = CACHE.get_in_out(get_session_id(), model, input)
            if output_to_use is not None:
                result = json_to_response(output_to_use, "OpenAI.responses.create")
            else:
                new_kwargs = dict(kwargs)
                new_kwargs["messages"] = input_to_use
                result = original_create(**new_kwargs)  # This might be a coroutine
                CACHE.cache_output(get_session_id(), node_id, result, "OpenAI.responses.create")

            send_graph_node_and_edges(
                node_id=node_id,
                input_dict=str(input_to_use),
                output_obj=result,
                source_node_ids=taint_origins,
                model=model,
                api_type="OpenAI.responses.create",
            )
            return taint_wrap(result, [node_id])

    completions.create = patched_create.__get__(completions, CompletionsClass)


"""
OpenAI assistant patches. OpenAI assistants are three calls:

client.beta.assistants.create(...) # just propagate taint
client.beta.threads.create(...) # Inputs are defined here. Create DB entry, check for input overwrite. Don't send to server.
client.beta.threads.runs.create_and_poll(...) # Output is produced here. Use existing DB entry to store output, send to server.

TODO: Output overwrites are not supported.
"""


def patch_openai_beta_threads_runs_create_and_poll(runs):
    original_function = runs.create_and_poll

    def patched_create_and_poll(self, **kwargs):
        api_type = "OpenAI.beta.threads.create"
        client = self._client
        thread_id = kwargs.get("thread_id")
        assistant_id = kwargs.get("assistant_id")

        # Get model information from assistant
        model = "unknown"
        if assistant_id:
            try:
                assistant = client.beta.assistants.retrieve(assistant_id)
                model = assistant.model
            except Exception:
                model = "unknown"

        # 1. Get inputs
        # Full input dict (returned dict is ordered).
        input_dict = get_input_dict(original_function, **kwargs)
        # Input object with actual thread content (last message). Read-only.
        input_obj = client.beta.threads.messages.list(thread_id=thread_id).data[0]
        # Overwrite model to get cached result.
        input_obj.model = model

        # 2. Get taint origins.
        taint_origins = get_taint_origins(input_dict)

        # 3. Get cached result or call LLM.
        # NOTE: Editing attachments is not supported.
        # TODO: Caching inputs and outputs currently not supported.
        # TODO: Output caching.
        cachable_input = get_cachable_input_openai_beta_threads_create(input_obj)
        _, _, node_id = CACHE.get_in_out(cachable_input, api_type)
        # input_dict = overwrite_input(original_function, **kwargs)
        # input_dict["messages"][-1]["content"] = input_to_use["messages"]
        # input_dict['messages'][-1]['attachments'] = input_to_use["attachments"]
        result = original_function(**input_dict)  # Call LLM.
        # CACHE.cache_output(node_id, result)

        # 4. Get actual, ultimate response.
        output_obj = client.beta.threads.messages.list(thread_id=thread_id).data[0]

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_obj,
            output_obj=output_obj,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 5. Taint the output object and return it.
        return taint_wrap(result, [node_id])

    runs.create_and_poll = patched_create_and_poll.__get__(runs, type(original_function))


def patch_openai_beta_assistants_create(assistants_instance):
    original_function = assistants_instance.create

    def patched_function(*args, **kwargs):
        # Collect taint origins from all args and kwargs
        input_dict = get_input_dict(original_function, *args, **kwargs)
        taint_origins = get_taint_origins(input_dict)
        # Call the original method
        result = original_function(*args, **kwargs)
        # Propagate taint
        return taint_wrap(result, list(taint_origins))

    assistants_instance.create = patched_function


def patch_openai_beta_threads_create(threads_instance):
    original_function = threads_instance.create

    def patched_function(*args, **kwargs):
        api_type = "OpenAI.beta.threads.create"
        # 1. Get taint origins.
        input_dict = get_input_dict(original_function, *args, **kwargs)
        taint_origins = get_taint_origins(input_dict)

        # 2. Get input to use and create thread.
        # We need to cache an input object that does not depend on
        # dynamically assigned OpenAI ids.
        cachable_input = get_cachable_input_openai_beta_threads_create(input_dict)
        input_to_use, _, _ = CACHE.get_in_out(cachable_input, api_type)
        input_dict["messages"][-1]["content"] = input_to_use["messages"]
        # FIXME: Overwriting attachments is not supported. Need UI support and
        # handle caveat that OAI can delete files online (and reassign IDs
        # different than the cached ones). Therefore below is commented out.
        # input_dict['messages'][-1]['attachments'] = input_to_use["attachments"]
        result = original_function(**input_dict)

        # 3. Taint and return.
        return taint_wrap(result, taint_origins)

    threads_instance.create = patched_function


def patch_openai_files_create(files_resource):
    try:
        from openai import AsyncOpenAI
        from openai.resources.files import AsyncFiles, Files
    except ImportError:
        return

    asynchronous = files_resource._client.__class__ == AsyncOpenAI
    FilesClass = Files
    if asynchronous:
        FilesClass = AsyncFiles

    original_create = files_resource.create

    if asynchronous:

        async def patched_create(self, **kwargs):
            # Extract file argument
            file_arg = kwargs.get("file")
            if isinstance(file_arg, tuple) and len(file_arg) >= 2:
                file_name = file_arg[0]
                fileobj = file_arg[1]
            elif hasattr(file_arg, "read"):
                fileobj = file_arg
                file_name = getattr(fileobj, "name", "unknown")
            else:
                raise ValueError(
                    "The 'file' argument must be a tuple (filename, fileobj, content_type) or a file-like object."
                )

            # Create a copy of the file content before the original API call consumes it
            fileobj.seek(0)
            file_content = fileobj.read()
            fileobj.seek(0)

            # Create a BytesIO object with the content for our cache functions
            fileobj_copy = BytesIO(file_content)
            fileobj_copy.name = getattr(fileobj, "name", "unknown")

            # Call the original method
            result = await original_create(**kwargs)
            # Get file_id from result
            file_id = getattr(result, "id", None)
            if file_id is None:
                raise ValueError("OpenAI did not return a file id after file upload.")
            CACHE.cache_file(file_id, file_name, fileobj_copy)
            # Propagate taint from fileobj if present
            taint_origins = get_taint_origins(fileobj)
            return taint_wrap(result, taint_origins)

    else:

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
                raise ValueError(
                    "The 'file' argument must be a tuple (filename, fileobj, content_type) or a file-like object."
                )

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

    files_resource.create = patched_create.__get__(files_resource, FilesClass)


def v1_openai_patch():
    """
    Patch openai.ChatCompletion.create (v1/classic API) to use persistent cache and edits.
    """
    try:
        import openai
    except ImportError:
        logger.info("OpenAI not installed, skipping OpenAI v1 patches")
        return

    # raise NotImplementedError
    original_create = getattr(openai.ChatCompletion, "create", None)
    if original_create is None:
        return

    def patched_create(*args, **kwargs):
        # Extract model and messages
        model = kwargs.get("model", args[0] if args else None)
        messages = kwargs.get("messages", args[1] if len(args) > 1 else None)
        # Use get_raw if present
        if hasattr(model, "get_raw"):
            model = model.get_raw()
        if hasattr(messages, "get_raw"):
            messages = messages.get_raw()
        # Use persistent cache/edits
        input_to_use, output_to_use, node_id = CACHE.get_in_out(
            get_session_id(), model, str(messages)
        )

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
            CACHE.cache_output(get_session_id(), node_id, result, "openai_v1")

        # Send to server (graph node/edges)
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_to_use,
            output_obj=result,
            source_node_ids=taint_origins,
            model=model,
            api_type="openai_v1",
        )

        # Wrap and return
        return taint_wrap(result, [node_id])

    openai.ChatCompletion.create = patched_create
