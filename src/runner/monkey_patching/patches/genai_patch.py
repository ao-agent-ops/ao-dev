from functools import wraps
from ao.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from ao.server.database_manager import DB
from ao.common.logger import logger
from ao.server.ast_helpers import get_taint_origins
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

        # Get taint origins (did another LLM produce the input?)
        # NOTE: genai uses get_taint_origins(input_dict) instead of ACTIVE_TAINT
        taint_origins = get_taint_origins(input_dict)
        active_taint = list(builtins.ACTIVE_TAINT.get())

        # Check if this endpoint should be patched
        path = input_dict.get("path", "")

        print(f"\n[DEBUG_TAINT] === genai_patch (async_request) ===")
        print(f"[DEBUG_TAINT]   path: {path}")
        print(f"[DEBUG_TAINT]   ACTIVE_TAINT: {active_taint}")
        print(f"[DEBUG_TAINT]   taint_origins from input_dict: {taint_origins}")

        if not is_whitelisted_endpoint(path):
            result = await original_function(*args, **kwargs)
            print(f"[DEBUG_TAINT]   (non-whitelisted, returning with taint_wrap)")
            return taint_wrap(result, taint_origins)

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

        # Taint the output object and return it
        print(f"[DEBUG_TAINT]   Returning with taint_wrap node_id: [{cache_output.node_id}]")
        return taint_wrap(cache_output.output, [cache_output.node_id])

    bound_obj.async_request = patched_function.__get__(bound_obj, bound_cls)
