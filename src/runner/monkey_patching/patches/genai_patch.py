from functools import wraps
from ao.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from ao.server.database_manager import DB
from ao.common.logger import logger
from ao.common.utils import is_whitelisted_endpoint
import builtins


def genai_patch():
    """
    Patch google.genai's BaseApiClient to intercept async_request calls.
    """
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
    """
    Patch the async_request method on a BaseApiClient instance.
    This method is called for non-streaming async requests.
    """
    original_function = bound_obj.async_request

    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        api_type = "genai.BaseApiClient.async_request"

        # Get full input dict
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # Get taint origins from ACTIVE_TAINT (set by exec_func)
        taint_origins = list(builtins.ACTIVE_TAINT.get())

        # Check if this endpoint should be patched
        path = input_dict.get("path", "")

        if not is_whitelisted_endpoint(path):
            result = await original_function(*args, **kwargs)
            return result  # No wrapping here, exec_func will use existing taint

        # Get result from cache or call LLM
        cache_output = DB.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = await original_function(**cache_output.input_dict)
            DB.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

        # Tell server that this LLM call happened
        send_graph_node_and_edges(
            node_id=cache_output.node_id,
            input_dict=cache_output.input_dict,
            output_obj=cache_output.output,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # Set the new taint in escrow for exec_func to wrap with
        builtins.ACTIVE_TAINT.set([cache_output.node_id])
        return cache_output.output  # No wrapping here, exec_func will wrap

    bound_obj.async_request = patched_function.__get__(bound_obj, bound_cls)
