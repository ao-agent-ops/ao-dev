from functools import wraps
from aco.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from aco.server.cache_manager import CACHE
from aco.common.logger import logger
from aco.runner.taint_wrappers import get_taint_origins, taint_wrap


def anthropic_patch():
    """
    Patch Anthropic API to use persistent cache and edits.
    """
    try:
        import anthropic
    except ImportError:
        logger.info("Anthropic not installed, skipping Anthropic patches")
        return

    original_init = anthropic.Anthropic.__init__

    @wraps(original_init)
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        patch_anthropic_messages_create(self.messages)
        patch_anthropic_files_upload(self.beta.files)
        patch_anthropic_files_list(self.beta.files)
        patch_anthropic_files_retrieve_metadata(self.beta.files)
        patch_anthropic_files_delete(self.beta.files)

    anthropic.Anthropic.__init__ = new_init


def patch_anthropic_messages_create(messages_instance):
    try:
        from anthropic.resources.messages import Messages
    except ImportError:
        return

    # FIXME: Messages with attachments don't work (won't be cached and displayed)
    original_function = messages_instance.create

    # Patched function (executed instead of Anthropic.messages.create)
    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "Anthropic.messages.create"

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

    # Install patch.
    messages_instance.create = patched_function.__get__(messages_instance, Messages)


def patch_anthropic_files_upload(files_instance):
    try:
        from anthropic.resources.beta.files import Files
    except ImportError:
        return

    original_function = files_instance.upload

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # Extract file argument
        file_arg = kwargs.get("file")
        file_name = "unknown"

        if hasattr(file_arg, "name"):
            file_name = file_arg.name
        elif hasattr(file_arg, "read"):
            file_name = getattr(file_arg, "name", "uploaded_file")

        # Call original method
        result = original_function(*args, **kwargs)

        # Cache the file if we have caching enabled
        file_id = getattr(result, "id", None)
        if file_id and file_arg:
            CACHE.cache_file(file_id, file_name, file_arg)

        # Propagate taint from file input
        taint_origins = get_taint_origins(file_arg)
        return taint_wrap(result, taint_origins)

    # Install patch.
    files_instance.upload = patched_function.__get__(files_instance, Files)


def patch_anthropic_files_list(files_instance):
    try:
        from anthropic.resources.beta.files import Files
    except ImportError:
        return

    original_function = files_instance.list

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # Call original method
        result = original_function(*args, **kwargs)

        # Propagate taint from any input arguments
        taint_origins = get_taint_origins(args) + get_taint_origins(kwargs)
        return taint_wrap(result, taint_origins)

    # Install patch.
    files_instance.list = patched_function.__get__(files_instance, Files)


def patch_anthropic_files_retrieve_metadata(files_instance):
    """
    Patch the .retrieve_metadata method of an Anthropic files instance to handle taint propagation.
    """
    try:
        from anthropic.resources.beta.files import Files
    except ImportError:
        return

    original_function = files_instance.retrieve_metadata

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # Call original method
        result = original_function(*args, **kwargs)

        # Propagate taint from any input arguments
        taint_origins = get_taint_origins(args) + get_taint_origins(kwargs)
        return taint_wrap(result, taint_origins)

    # Install patch.
    files_instance.retrieve_metadata = patched_function.__get__(files_instance, Files)


def patch_anthropic_files_delete(files_instance):
    try:
        from anthropic.resources.beta.files import Files
    except ImportError:
        return

    original_function = files_instance.delete

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # Call original method
        result = original_function(*args, **kwargs)

        # Propagate taint from any input arguments
        taint_origins = get_taint_origins(args) + get_taint_origins(kwargs)
        return taint_wrap(result, taint_origins)

    # Install patch.
    files_instance.delete = patched_function.__get__(files_instance, Files)
