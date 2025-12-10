from functools import wraps
from io import BytesIO
from aco.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from aco.server.database_manager import DB
from aco.common.logger import logger
from aco.runner.taint_wrappers import get_taint_origins, taint_wrap


# ===========================================================
# Patches for OpenAI Client
# ===========================================================


def openai_patch():
    try:
        from openai import OpenAI
    except ImportError:
        logger.info("OpenAI not installed, skipping OpenAI patches")
        return

    def create_patched_init(original_init):

        @wraps(original_init)
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            patch_openai_responses_create(self.responses)
            patch_openai_chat_completions_create(self.chat.completions)
            patch_openai_beta_assistants_create(self.beta.assistants)
            patch_openai_beta_threads_create(self.beta.threads)
            patch_openai_beta_threads_runs_create_and_poll(self.beta.threads.runs)
            patch_openai_files_create(self.files)

        return patched_init

    original_init = OpenAI.__init__
    OpenAI.__init__ = create_patched_init(original_init)


# Patch for OpenAI.responses.create is called patch_openai_responses_create
def patch_openai_responses_create(responses):
    try:
        from openai.resources.responses import Responses
    except ImportError:
        return

    # Original OpenAI.responses.create function
    original_function = responses.create

    # Patched function (executed instead of OpenAI.responses.create)
    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "OpenAI.responses.create"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        cache_output = DB.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = original_function(**cache_output.input_dict)  # Call LLM.
            DB.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=cache_output.node_id,
            input_dict=cache_output.input_dict,
            output_obj=cache_output.output,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(cache_output.output, [cache_output.node_id])

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
    def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "OpenAI.chat.completions.create"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # HACK: We need content to be string. Just do quick and dirty for BIRD.
        for message in input_dict.get("messages", []):
            if "content" in message:
                message["content"] = str(message["content"])

        # 4. Get result from cache or call LLM.
        cache_output = DB.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = original_function(**cache_output.input_dict)  # Call LLM.
            DB.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=cache_output.node_id,
            input_dict=cache_output.input_dict,
            output_obj=cache_output.output,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(cache_output.output, [cache_output.node_id])

    # Install patch.
    completions.create = patched_function.__get__(completions, Completions)


"""
Files are uploaded to OpenAI, which returns a reference to them.
OpenAI keeps them around for ~30 days and deletes them after. Users
may call files.create only providing a file-like object (no path).

Therefore, we allow the user to cache the files they upload locally
(i.e., create copies of the files and associate them with the 
corresponding requests).
"""


def patch_openai_files_create(files_resource):
    try:
        from openai.resources.files import Files
    except ImportError:
        return

    original_function = files_resource.create

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
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
        result = original_function(*args, **kwargs)
        # Get file_id from result
        file_id = getattr(result, "id", None)
        DB.cache_file(file_id, file_name, fileobj_copy)
        # Pass on taint from fileobj if present.
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
    try:
        from openai.resources.beta.assistants import Assistants
    except ImportError:
        return

    original_function = assistants_instance.create

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # Collect taint origins from all args and kwargs
        input_dict = get_input_dict(original_function, *args, **kwargs)
        taint_origins = get_taint_origins(input_dict)
        # Call the original method
        result = original_function(*args, **kwargs)
        # Propagate taint
        return taint_wrap(result, list(taint_origins))

    assistants_instance.create = patched_function.__get__(assistants_instance, Assistants)


def patch_openai_beta_threads_create(threads_instance):
    try:
        from openai.resources.beta.threads import Threads
    except ImportError:
        return

    original_function = threads_instance.create

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        """
        This patch is unusual since no LLM is run here. The API call creates
        a thread which is then run in threads.create_and_poll. However, inputs
        need to be overwritten here. So the patch only checks if its input should
        be overwritten and doesn't cache an output / check for a cached output.
        """
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "OpenAI.beta.threads.create"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get input to use and run API call with it.
        cache_output = DB.get_in_out(input_dict, api_type)
        result = original_function(**cache_output.input_dict)

        # 5. We don't report this call to the server (no LLM inference).

        # 6. Taint and return.
        return taint_wrap(result, taint_origins)

    threads_instance.create = patched_function.__get__(threads_instance, Threads)


def patch_openai_beta_threads_runs_create_and_poll(runs):
    try:
        from openai.resources.beta.threads.runs import Runs
    except ImportError:
        return

    original_function = runs.create_and_poll

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        """
        This patch is unusual since the input and output are defined/returned
        in other API calls. Inputs are defined in OpenAI.beta.threads.create
        and the output is obtained in OpenAI.beta.threads.messages.list.

        We get the input object that was uploaded in threads.create. This object
        is "read-only", so we use it as a cache key but overwrites must be applied
        in beta.threads.create. We further cache the output by invoking
        threads.messages.list.

        FIXME: Keeping inputs the same but changing model will lead to cache hit.
        """
        # 1. Define API type, get client and assistant.
        api_type = "OpenAI.beta.threads.create_and_poll"
        client = self._client
        thread_id = kwargs.get("thread_id")
        assistant_id = kwargs.get("assistant_id")
        assistant = client.beta.assistants.retrieve(assistant_id)

        # 2. Get input_dict and input object that was used in threads.create.
        input_dict = get_input_dict(original_function, *args, **kwargs)
        input_obj = client.beta.threads.messages.list(thread_id=thread_id).data[0]
        # HACK: The model is not denoted in input_obj so we just add it here.
        # FIXME: We first set it to "unknown" because we don't know the model in
        # threads.create, and this allows for cache hits. We then set it to the
        # actual model for the UI. Keeping the inputs fixed but changing the model
        # will lead to cache hits.
        input_obj.model = "unknown"

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Always call the LLM (no caching for runs since they're stateful)
        cache_output = DB.get_in_out(input_obj, api_type)
        run_result = original_function(**input_dict)  # Call LLM.

        # Get the actual message result for the server reporting
        message_result = client.beta.threads.messages.list(thread_id=thread_id).data[0]

        # 5. Tell server that this LLM call happened.
        # HACK: The model is not denoted in input_obj so we just add it here.
        input_obj.model = assistant.model
        send_graph_node_and_edges(
            node_id=cache_output.node_id,
            input_dict=input_obj,
            output_obj=message_result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return the run result (not the message)
        return taint_wrap(run_result, [cache_output.node_id])

    runs.create_and_poll = patched_function.__get__(runs, Runs)


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

    original_init = AsyncOpenAI.__init__
    AsyncOpenAI.__init__ = create_patched_init(original_init)


# Patch for OpenAI.responses.create is called patch_openai_responses_create
def patch_async_openai_responses_create(responses):
    try:
        from openai.resources.responses import AsyncResponses
    except ImportError:
        return

    # Original OpenAI.responses.create function
    original_function = responses.create

    # Patched function (executed instead of OpenAI.responses.create)
    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "AsyncOpenAI.responses.create"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        cache_output = DB.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = await original_function(**cache_output.input_dict)  # Call LLM.
            DB.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=cache_output.node_id,
            input_dict=cache_output.input_dict,
            output_obj=cache_output.output,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(cache_output.output, [cache_output.node_id])

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
    try:
        from openai.resources.files import AsyncFiles
    except ImportError:
        return

    original_function = files_resource.create

    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
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
        DB.cache_file(file_id, file_name, fileobj_copy)
        # Propagate taint from fileobj if present
        taint_origins = get_taint_origins(fileobj)
        return taint_wrap(result, taint_origins)

    # Install patch.
    files_resource.create = patched_function.__get__(files_resource, AsyncFiles)


def patch_async_openai_chat_completions_create(completions):
    try:
        from openai.resources.chat.completions import AsyncCompletions
    except ImportError:
        return

    # Original AsyncOpenAI.chat.completions.create
    original_function = completions.create

    # Patched function (executed instead of AsyncOpenAI.chat.completions.create)
    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "AsyncOpenAI.chat.completions.create"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        cache_output = DB.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = await original_function(**cache_output.input_dict)  # Call LLM.
            DB.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=cache_output.node_id,
            input_dict=cache_output.input_dict,
            output_obj=cache_output.output,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Taint the output object and return it.
        return taint_wrap(cache_output.output, taint_origin=[cache_output.node_id])

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
    try:
        from openai.resources.beta.assistants import AsyncAssistants
    except ImportError:
        return

    original_function = assistants_instance.create

    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        # Collect taint origins from all args and kwargs
        input_dict = get_input_dict(original_function, *args, **kwargs)
        taint_origins = get_taint_origins(input_dict)
        # Call the original method
        result = await original_function(*args, **kwargs)
        # Propagate taint
        return taint_wrap(result, list(taint_origins))

    assistants_instance.create = patched_function.__get__(assistants_instance, AsyncAssistants)


def patch_async_openai_beta_threads_create(threads_instance):
    try:
        from openai.resources.beta.threads import AsyncThreads
    except ImportError:
        return

    original_function = threads_instance.create

    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        api_type = "OpenAI.beta.threads.create"
        # 1. Get taint origins.
        input_dict = get_input_dict(original_function, *args, **kwargs)
        taint_origins = get_taint_origins(input_dict)

        # 2. Get input to use and create thread.
        # We need to cache an input object that does not depend on
        # dynamically assigned OpenAI ids.
        cache_output = DB.get_in_out(input_dict, api_type)

        # FIXME: Overwriting attachments is not supported. Need UI support and
        # handle caveat that OAI can delete files online (and reassign IDs
        # different than the cached ones). Therefore below is commented out.
        # input_dict['messages'][-1]['attachments'] = cache_output.input_dict["attachments"]
        result = await original_function(**cache_output.input_dict)

        # 3. Taint and return.
        return taint_wrap(result, taint_origins)

    threads_instance.create = patched_function.__get__(threads_instance, AsyncThreads)


def patch_async_openai_beta_threads_runs_create_and_poll(runs):
    try:
        from openai.resources.beta.threads.runs import AsyncRuns
    except ImportError:
        return

    original_function = runs.create_and_poll

    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
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
        cache_output = DB.get_in_out(input_dict, api_type)

        # input_dict = overwrite_input(original_function, **kwargs)
        # input_dict["messages"][-1]["content"] = input_to_use["messages"]
        # input_dict['messages'][-1]['attachments'] = input_to_use["attachments"]

        result = await original_function(**input_dict)  # Call LLM.
        # DB.cache_output(node_id, result)

        # 4. Get actual, ultimate response.
        output_obj = (await client.beta.threads.messages.list(thread_id=thread_id)).data[0]

        # 5. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=cache_output.node_id,
            input_dict=input_obj,
            output_obj=output_obj,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 5. Taint the output object and return it.
        return taint_wrap(result, [cache_output.node_id])

    runs.create_and_poll = patched_function.__get__(runs, AsyncRuns)
