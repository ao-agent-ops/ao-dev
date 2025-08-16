import asyncio
import inspect
import functools
import json
import threading
import functools
from io import BytesIO
from agent_copilot.context_manager import get_session_id
from runtime_tracing.utils import get_input_dict, send_graph_node_and_edges
from workflow_edits.cache_manager import CACHE
from common.logger import logger
from workflow_edits.utils import get_input, get_model_name, get_output_string
from runtime_tracing.taint_wrappers import get_taint_origins, taint_wrap


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

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        patch_anthropic_messages_create(self.messages)
        patch_anthropic_files_upload(self.beta.files)
        patch_anthropic_files_list(self.beta.files)
        patch_anthropic_files_retrieve_metadata(self.beta.files)
        patch_anthropic_files_delete(self.beta.files)

    anthropic.Anthropic.__init__ = new_init


def patch_anthropic_messages_create(messages_instance):
    original_function = messages_instance.create

    # Patched function (executed instead of Anthropic.messages.create)
    def patched_function(*args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "Anthropic.messages.create"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Extract inputs from messages.
        # FIXME: We're only considering the last message.
        # TODO: Can be simplified?

        # 5. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            result = original_function(**input_to_use)  # Call LLM.
            CACHE.cache_output(node_id, result)

        # 6. Tell server that this LLM call happened.
        send_graph_node_and_edges(
            node_id=node_id,
            input_dict=input_to_use,
            output_obj=result,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        return taint_wrap(result, [node_id])

    messages_instance.create = patched_function


def patch_anthropic_files_upload(files_instance):
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
