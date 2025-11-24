from functools import wraps
from io import BytesIO
from aco.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from aco.server.cache_manager import CACHE
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
            patch_openai_post(self, type(self))
            # patch_openai_files_create(self.files)

        return patched_init

    original_init = OpenAI.__init__
    OpenAI.__init__ = create_patched_init(original_init)


def patch_openai_post(bound_obj, bound_cls):
    # bound_obj has a _post method, which we are patching
    original_function = bound_obj.post

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):

        api_type = "OpenAI.SyncAPIClient.post"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        if not input_dict["path"] in ["/responses", "/chat/completions"]:
            result = original_function(*args, **kwargs)
            return taint_wrap(result, taint_origins)

        # 4. Get result from cache or call LLM.
        cache_output = CACHE.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = original_function(**cache_output.input_dict)  # Call LLM.
            CACHE.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

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

    bound_obj.post = patched_function.__get__(bound_obj, bound_cls)


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
        CACHE.cache_file(file_id, file_name, fileobj_copy)
        # Pass on taint from fileobj if present.
        taint_origins = get_taint_origins(fileobj)
        return taint_wrap(result, taint_origins)

    # Install patch.
    files_resource.create = patched_function.__get__(files_resource, Files)


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
            patch_async_openai_post(self, type(self))
            patch_async_openai_files_create(self.files)

        return patched_init

    original_init = AsyncOpenAI.__init__
    AsyncOpenAI.__init__ = create_patched_init(original_init)


def patch_async_openai_post(bound_obj, bound_cls):
    # bound_obj has a post method, which we are patching
    original_function = bound_obj.post

    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):

        api_type = "AsyncOpenAI.AsyncAPIClient.post"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        if not input_dict["path"] in ["/responses", "/chat/completions"]:
            result = await original_function(*args, **kwargs)
            return taint_wrap(result, taint_origins)

        # 4. Get result from cache or call LLM.
        cache_output = CACHE.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = await original_function(**cache_output.input_dict)  # Call LLM.
            CACHE.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

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

    bound_obj.post = patched_function.__get__(bound_obj, bound_cls)


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
        CACHE.cache_file(file_id, file_name, fileobj_copy)
        # Propagate taint from fileobj if present
        taint_origins = get_taint_origins(fileobj)
        return taint_wrap(result, taint_origins)

    # Install patch.
    files_resource.create = patched_function.__get__(files_resource, AsyncFiles)
