from functools import wraps
from ao.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from ao.server.database_manager import DB
from ao.common.logger import logger
import builtins


# ===========================================================
# Patches for MCP ClientSession
# ===========================================================


def mcp_patch():
    try:
        from mcp.client.session import ClientSession
    except ImportError:
        logger.info("MCP not installed, skipping MCP patches")
        return

    def create_patched_init(original_init):

        @wraps(original_init)
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            patch_mcp_send_request(self, type(self))

        return patched_init

    ClientSession.__init__ = create_patched_init(ClientSession.__init__)


def patch_mcp_send_request(bound_obj, bound_cls):
    # bound_obj has a send_request method, which we are patching
    original_function = bound_obj.send_request

    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        api_type = "MCP.ClientSession.send_request"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins from ACTIVE_TAINT (set by exec_func)
        taint_origins = list(builtins.ACTIVE_TAINT.get())

        # Check if this is a tools/call request
        # The method is at input_dict["request"].root.method
        request = input_dict.get("request")
        method = getattr(getattr(request, "root", None), "method", None) if request else None

        if method != "tools/call":
            result = await original_function(*args, **kwargs)
            return result  # No wrapping here, exec_func will use existing escrow

        # 4. Get result from cache or call tool.
        cache_output = DB.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = await original_function(**cache_output.input_dict)
            DB.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)
        else:
            cache_output.output = input_dict["result_type"].model_validate(cache_output.output)

        # 5. Tell server that this tool call happened.
        send_graph_node_and_edges(
            node_id=cache_output.node_id,
            input_dict=cache_output.input_dict,
            output_obj=cache_output.output,
            source_node_ids=taint_origins,
            api_type=api_type,
        )

        # 6. Set the new taint in escrow for exec_func to wrap with.
        builtins.ACTIVE_TAINT.set([cache_output.node_id])
        return cache_output.output  # No wrapping here, exec_func will wrap

    bound_obj.send_request = patched_function.__get__(bound_obj, bound_cls)
