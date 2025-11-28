from functools import wraps
from aco.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from aco.server.cache_manager import CACHE
from aco.common.logger import logger
from aco.runner.taint_wrappers import get_taint_origins, taint_wrap


# ===========================================================
# Patches for Anthropic Client
# ===========================================================


def anthropic_patch():
    try:
        from anthropic import Anthropic
    except ImportError:
        logger.info("Anthropic not installed, skipping Anthropic patches")
        return

    def create_patched_init(original_init):

        @wraps(original_init)
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            patch_anthropic_post(self, type(self))

        return patched_init

    original_init = Anthropic.__init__
    Anthropic.__init__ = create_patched_init(original_init)


def patch_anthropic_post(bound_obj, bound_cls):
    # bound_obj has a _post method, which we are patching
    original_function = bound_obj.post

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):

        api_type = "Anthropic.SyncAPIClient.post"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        if not input_dict["path"] in ["/v1/messages"]:
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


# ===========================================================
# Patches for AsyncAnthropic Client
# ===========================================================


def async_anthropic_patch():
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        logger.info("Anthropic not installed, skipping AsyncAnthropic patches")
        return

    def create_patched_init(original_init):

        @wraps(original_init)
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            patch_async_anthropic_post(self, type(self))

        return patched_init

    original_init = AsyncAnthropic.__init__
    AsyncAnthropic.__init__ = create_patched_init(original_init)


def patch_async_anthropic_post(bound_obj, bound_cls):
    # bound_obj has a post method, which we are patching
    original_function = bound_obj.post

    @wraps(original_function)
    async def patched_function(self, *args, **kwargs):

        api_type = "AsyncAnthropic.AsyncAPIClient.post"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        if not input_dict["path"] in ["/v1/messages"]:
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
