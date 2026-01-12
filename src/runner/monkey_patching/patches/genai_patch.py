from functools import wraps
from ao.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from ao.server.database_manager import DB
from ao.common.logger import logger
from ao.common.utils import is_whitelisted_endpoint
import builtins


def genai_patch():
    try:
        from google.genai._api_client import BaseApiClient
    except ImportError:
        logger.info("google-genai not installed, skipping genai patches")
        return

    def create_patched_init(original_init):

        @wraps(original_init)
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            patch_genai_async_request(self, type(self))

        return patched_init

    BaseApiClient.__init__ = create_patched_init(BaseApiClient.__init__)


def patch_genai_async_request(bound_obj, bound_cls):
    original_function = bound_obj.async_request

    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        api_type = "genai.BaseApiClient.async_request"

        input_dict = get_input_dict(original_function, *args, **kwargs)
        taint_origins = builtins.TAINT_STACK.read()

        # genai doesn't expose full URL, only path
        path = input_dict.get("path", "")
        if not is_whitelisted_endpoint("*", path):
            return await original_function(*args, **kwargs)

        # Get result from cache or call LLM
        cache_output = DB.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = await original_function(**cache_output.input_dict)  # Call LLM
            DB.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

        # Send graph node to server
        send_graph_node_and_edges(
            node_id=cache_output.node_id,
            input_dict=cache_output.input_dict,
            output_obj=cache_output.output,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # Update TAINT_STACK so exec_func applies this node's taint to result
        builtins.TAINT_STACK.update([cache_output.node_id])
        return cache_output.output

    bound_obj.async_request = patched_function.__get__(bound_obj, bound_cls)
