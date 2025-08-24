from functools import wraps
from io import BytesIO
from runtime_tracing.utils import get_input_dict, send_graph_node_and_edges
from agent_copilot.context_manager import get_session_id
from workflow_edits.cache_manager import CACHE
from common.logger import logger
from runtime_tracing.taint_wrappers import get_taint_origins, taint_wrap


# ===========================================================
# Patches for OpenAI Client
# ===========================================================


def openai_patch():
    print("[openai_patch] Starting OpenAI patch application")
    try:
        from openai import OpenAI

        print(
            f"[openai_patch] OpenAI imported successfully, version: {getattr(__import__('openai'), '__version__', 'unknown')}"
        )
    except ImportError:
        print("[openai_patch] OpenAI not installed, skipping OpenAI patches")
        logger.info("OpenAI not installed, skipping OpenAI patches")
        return

    def create_patched_init(original_init):

        @wraps(original_init)
        def patched_init(self, *args, **kwargs):
            print(f"[openai_patch] OpenAI.__init__ called with args={args}, kwargs={kwargs}")
            original_init(self, *args, **kwargs)
            print("[openai_patch] Original OpenAI.__init__ completed, now applying sub-patches")
            patch_openai_responses_create(self.responses)
            patch_openai_chat_completions_create(self.chat.completions)
            patch_openai_beta_assistants_create(self.beta.assistants)
            patch_openai_beta_threads_create(self.beta.threads)
            patch_openai_beta_threads_runs_create_and_poll(self.beta.threads.runs)
            patch_openai_files_create(self.files)
            print("[openai_patch] All OpenAI sub-patches applied successfully")

        return patched_init

    print("[openai_patch] Patching OpenAI.__init__")
    OpenAI.__init__ = create_patched_init(OpenAI.__init__)
    print("[openai_patch] OpenAI.__init__ patched successfully")


# Patch for OpenAI.responses.create is called patch_openai_responses_create
def patch_openai_responses_create(responses):
    # Maybe the user doesn't have OpenAI installed.
    print("[openai_patch] Patching OpenAI.responses.create")
    try:
        from openai.resources.responses import Responses
    except ImportError:
        print("[openai_patch] Failed to import openai.resources.responses.Responses")
        return

    # Original OpenAI.responses.create function
    original_function = responses.create
    # Get the unbound function for signature inspection to avoid "invalid method signature" error
    # Use the class function directly as it has the correct signature for inspect.signature()
    from openai.resources.responses import Responses

    unbound_function = Responses.create

    # Patched function (executed instead of OpenAI.responses.create)
    @wraps(original_function)
    def patched_function(*args, **kwargs):

        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "OpenAI.responses.create"

        # 2. Get full input dict.
        input_dict = get_input_dict(unbound_function, *args, **kwargs)

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

    # Install patch.
    responses.create = patched_function.__get__(responses, Responses)


def patch_openai_chat_completions_create(completions):
    try:
        from openai.resources.chat.completions import Completions
    except ImportError:
        return

    # Original OpenAI.chat.completions.create
    original_function = completions.create

    # Patched function (executed instead of OpenAI.chat.completions.create)
    @wraps(original_function)
    def patched_function(*args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "OpenAI.chat.completions.create"

        # 2. Get full input dict.
        # "messages" is an iterable over a struct that has three fields: "content", "role",
        # Optional: "name" --- "name" is an optional name for the participant.
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

    # Install patch.
    completions.create = patched_function.__get__(completions, Completions)


"""
Files are uploaded to OpenAI, which returns a reference to them.
OpenAI keeps them around for ~30 days and deletes them after. Users
may call files.create only providing a file-like object (no path).

Therefore we allow the user to cache the files he uploads locally
(i.e., create copies of the files and associate them with the 
corresponding requests).
"""


def patch_openai_files_create(files_resource):
    # Maybe the user doesn't have OpenAI installed.
    try:
        from openai.resources.files import Files
    except ImportError:
        return

    original_function = files_resource.create

    @wraps(original_function)
    def patched_function(self, **kwargs):
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
        result = original_function(**kwargs)
        # Get file_id from result
        file_id = getattr(result, "id", None)
        if file_id is None:
            raise ValueError("OpenAI did not return a file id after file upload.")
        CACHE.cache_file(file_id, file_name, fileobj_copy)
        # Propagate taint from fileobj if present
        taint_origins = get_taint_origins(fileobj)
        return taint_wrap(result, taint_origins)

    # Install patch.
    files_resource.create = patched_function.__get__(files_resource, Files)


"""
OpenAI assistant patches. OpenAI assistants are three calls:

client.beta.assistants.create(...) # just propagate taint
client.beta.threads.create(...) # Inputs are defined here. Create DB entry, check for input overwrite. Don't send to server.
client.beta.threads.runs.create_and_poll(...) # Output is produced here. Use existing DB entry to store output, send to server.

TODO: Output overwrites are not supported.
"""


def patch_openai_beta_assistants_create(assistants_instance):
    original_function = assistants_instance.create

    @wraps(original_function)
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

    @wraps(original_function)
    def patched_function(*args, **kwargs):
        api_type = "OpenAI.beta.threads.create"
        # 1. Get taint origins.
        input_dict = get_input_dict(original_function, *args, **kwargs)
        taint_origins = get_taint_origins(input_dict)

        # 2. Get input to use and create thread.
        input_to_use, _, _ = CACHE.get_in_out(input_dict, api_type)

        # FIXME: Overwriting attachments is not supported. Also need to
        # implement in UI.
        result = original_function(**input_to_use)

        # 3. Taint and return.
        return taint_wrap(result, taint_origins)

    threads_instance.create = patched_function


def patch_openai_beta_threads_runs_create_and_poll(runs):
    original_function = runs.create_and_poll

    @wraps(original_function)
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
        _, _, node_id = CACHE.get_in_out(input_obj, api_type, cache=False)

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


# ===========================================================
# Patches for AsyncOpenAI Client
# ===========================================================


def async_openai_patch():
    try:
        from openai import AsyncOpenAI
    except ImportError:
        logger.info("OpenAI not installed, skipping AsyncOpenAI patches")
        return

    def create_patched_init(original_init):

        @wraps(original_init)
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            patch_async_openai_responses_create(self.responses)
            patch_async_openai_chat_completions_create(self.chat.completions)
            patch_async_openai_beta_assistants_create(self.beta.assistants)
            patch_async_openai_beta_threads_create(self.beta.threads)
            patch_async_openai_beta_threads_runs_create_and_poll(self.beta.threads.runs)
            patch_async_openai_files_create(self.files)

        return patched_init

    AsyncOpenAI.__init__ = create_patched_init(AsyncOpenAI.__init__)


# Patch for OpenAI.responses.create is called patch_openai_responses_create
def patch_async_openai_responses_create(responses):
    # Maybe the user doesn't have OpenAI installed.
    try:
        from openai.resources.responses import AsyncResponses
    except ImportError:
        return

    # Original OpenAI.responses.create function
    original_function = responses.create

    # Patched function (executed instead of OpenAI.responses.create)
    @wraps(original_function)
    async def patched_function(*args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "AsyncOpenAI.responses.create"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            result = await original_function(**input_to_use)  # Call LLM.
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

    # Install patch.
    responses.create = patched_function.__get__(responses, AsyncResponses)


"""
Files are uploaded to OpenAI, which returns a reference to them.
OpenAI keeps them around for ~30 days and deletes them after. Users
may call files.create only providing a file-like object (no path).

Therefore we allow the user to cache the files he uploads locally
(i.e., create copies of the files and associate them with the 
corresponding requests).
"""


def patch_async_openai_files_create(files_resource):
    original_function = files_resource.create

    @wraps(original_function)
    async def patched_function(self, **kwargs):
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
        result = await original_function(**kwargs)
        # Get file_id from result
        file_id = getattr(result, "id", None)
        if file_id is None:
            raise ValueError("OpenAI did not return a file id after file upload.")
        CACHE.cache_file(file_id, file_name, fileobj_copy)
        # Propagate taint from fileobj if present
        taint_origins = get_taint_origins(fileobj)
        return taint_wrap(result, taint_origins)

    # Install patch.
    files_resource.create = patched_function


def patch_async_openai_chat_completions_create(completions):
    try:
        from openai.resources.chat.completions import AsyncCompletions
        from openai.types.chat import ChatCompletionMessageParam
    except ImportError:
        return

    # Original AsyncOpenAI.chat.completions.create
    original_function = completions.create

    # Patched function (executed instead of AsyncOpenAI.chat.completions.create)
    @wraps(original_function)
    async def patched_function(*args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "AsyncOpenAI.chat.completions.create"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            result = await original_function(**input_to_use)  # Call LLM.
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

    # Install patch.
    completions.create = patched_function.__get__(completions, AsyncCompletions)


"""
OpenAI assistant patches. OpenAI assistants are three calls:

client.beta.assistants.create(...) # just propagate taint
client.beta.threads.create(...) # Inputs are defined here. Create DB entry, check for input overwrite. Don't send to server.
client.beta.threads.runs.create_and_poll(...) # Output is produced here. Use existing DB entry to store output, send to server.

TODO: Output overwrites are not supported.
"""


def patch_async_openai_beta_assistants_create(assistants_instance):
    original_function = assistants_instance.create

    @wraps(original_function)
    async def patched_function(*args, **kwargs):
        # Collect taint origins from all args and kwargs
        input_dict = get_input_dict(original_function, *args, **kwargs)
        taint_origins = get_taint_origins(input_dict)
        # Call the original method
        result = await original_function(*args, **kwargs)
        # Propagate taint
        return taint_wrap(result, list(taint_origins))

    assistants_instance.create = patched_function


def patch_async_openai_beta_threads_create(threads_instance):
    original_function = threads_instance.create

    @wraps(original_function)
    async def patched_function(*args, **kwargs):
        api_type = "OpenAI.beta.threads.create"
        # 1. Get taint origins.
        input_dict = get_input_dict(original_function, *args, **kwargs)
        taint_origins = get_taint_origins(input_dict)

        # 2. Get input to use and create thread.
        # We need to cache an input object that does not depend on
        # dynamically assigned OpenAI ids.
        input_to_use, _, _ = CACHE.get_in_out(input_dict, api_type)

        # FIXME: Overwriting attachments is not supported. Need UI support and
        # handle caveat that OAI can delete files online (and reassign IDs
        # different than the cached ones). Therefore below is commented out.
        # input_dict['messages'][-1]['attachments'] = input_to_use["attachments"]
        result = await original_function(**input_to_use)

        # 3. Taint and return.
        return taint_wrap(result, taint_origins)

    threads_instance.create = patched_function


def patch_async_openai_beta_threads_runs_create_and_poll(runs):
    original_function = runs.create_and_poll

    @wraps(original_function)
    async def patched_create_and_poll(self, **kwargs):
        api_type = "OpenAI.beta.threads.create"
        client = self._client
        thread_id = kwargs.get("thread_id")
        assistant_id = kwargs.get("assistant_id")

        # Get model information from assistant
        model = "unknown"
        if assistant_id:
            try:
                assistant = await client.beta.assistants.retrieve(assistant_id)
                model = assistant.model
            except Exception:
                model = "unknown"

        # 1. Get inputs
        # Full input dict (returned dict is ordered).
        input_dict = get_input_dict(original_function, **kwargs)

        # Input object with actual thread content (last message). Read-only.
        input_obj = (await client.beta.threads.messages.list(thread_id=thread_id)).data[0]

        # Overwrite model to get cached result.
        input_obj.model = model

        # 2. Get taint origins.
        taint_origins = get_taint_origins(input_dict)

        # 3. Get cached result or call LLM.
        # NOTE: Editing attachments is not supported.
        # TODO: Caching inputs and outputs currently not supported.
        # TODO: Output caching.
        _, _, node_id = CACHE.get_in_out(input_dict, api_type)

        # input_dict = overwrite_input(original_function, **kwargs)
        # input_dict["messages"][-1]["content"] = input_to_use["messages"]
        # input_dict['messages'][-1]['attachments'] = input_to_use["attachments"]

        result = await original_function(**input_dict)  # Call LLM.
        # CACHE.cache_output(node_id, result)

        # 4. Get actual, ultimate response.
        output_obj = (await client.beta.threads.messages.list(thread_id=thread_id)).data[0]

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


def patch_async_openai_chat_completions_create(completions):
    try:
        from openai.resources.chat.completions import Completions
    except ImportError:
        return

    # Original OpenAI.chat.completions.create
    original_function = completions.create

    # Patched function (executed instead of OpenAI.chat.completions.create)
    @wraps(original_function)
    async def patched_function(*args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "AsyncOpenAI.chat.completions.create"

        # 2. Get full input dict.
        # "messages" is an iterable over a struct that has three fields: "content", "role",
        # Optional: "name" --- "name" is an optional name for the participant.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            result = await original_function(**input_to_use)  # Call LLM.
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

    # Install patch.
    completions.create = patched_function.__get__(completions, Completions)
