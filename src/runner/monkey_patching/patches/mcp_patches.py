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
            patch_mcp_call_tool(self)

        return patched_init

    original_init = ClientSession.__init__
    ClientSession.__init__ = create_patched_init(original_init)


def patch_mcp_call_tool(session_instance):
    try:
        from mcp.client.session import ClientSession
    except ImportError:
        return

    # Original MCP ClientSession.call_tool method
    original_function = session_instance.call_tool

    # Patched function (executed instead of ClientSession.call_tool)
    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "MCP.ClientSession.call_tool"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call tool.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            result = await original_function(*args, **kwargs)
            CACHE.cache_output(node_id, result)

        # 5. Tell server that this tool call happened.
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
    session_instance.call_tool = patched_function.__get__(session_instance, ClientSession)
