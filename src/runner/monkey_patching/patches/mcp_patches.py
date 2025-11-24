from functools import wraps
from aco.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from aco.server.cache_manager import CACHE
from aco.common.logger import logger
from aco.runner.taint_wrappers import get_taint_origins, taint_wrap


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
            patch_mcp_send_request(self)
            # patch_mcp_call_tool(self)

        return patched_init

    original_init = ClientSession.__init__
    ClientSession.__init__ = create_patched_init(original_init)


def patch_mcp_send_request(session_instance):
    try:
        from mcp.client.session import ClientSession
    except ImportError:
        return

    # Original MCP ClientSession.send_request method
    original_function = session_instance.send_request

    # Patched function (executed instead of ClientSession.send_request)
    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "MCP.ClientSession.send_request"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        method = input_dict["request"].root.method
        if not method in ["tools/call"]:
            result = await original_function(*args, **kwargs)
            return taint_wrap(result, taint_origins)

        # 4. Get result from cache or call tool.
        cache_output = CACHE.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = await original_function(**cache_output.input_dict)
            CACHE.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)
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

        # 6. Taint the output object and return it.
        return taint_wrap(cache_output.output, [cache_output.node_id])

    # Install patch.
    session_instance.send_request = patched_function.__get__(session_instance, ClientSession)


# def patch_mcp_call_tool(session_instance):
#     try:
#         from mcp.client.session import ClientSession
#     except ImportError:
#         return

#     # Original MCP ClientSession.call_tool method
#     original_function = session_instance.call_tool

#     # Patched function (executed instead of ClientSession.call_tool)
#     @wraps(original_function)
#     async def patched_function(self, *args, **kwargs):
#         # 1. Set API identifier to fully qualified name of patched function.
#         api_type = "MCP.ClientSession.call_tool"

#         # 2. Get full input dict.
#         input_dict = get_input_dict(original_function, *args, **kwargs)

#         # 3. Get taint origins (did another LLM produce the input?).
#         taint_origins = get_taint_origins(input_dict)

#         # 4. Get result from cache or call tool.
#         cache_output = CACHE.get_in_out(input_dict, api_type)
#         if cache_output.output is None:
#             result = await original_function(*args, **kwargs)
#             CACHE.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

#         # 5. Tell server that this tool call happened.
#         send_graph_node_and_edges(
#             node_id=cache_output.node_id,
#             input_dict=cache_output.input_dict,
#             output_obj=cache_output.output,
#             source_node_ids=taint_origins,
#             api_type=api_type,
#         )

#         # 6. Taint the output object and return it.
#         return taint_wrap(cache_output.output, [cache_output.node_id])

#     # Install patch.
#     session_instance.call_tool = patched_function.__get__(session_instance, ClientSession)
