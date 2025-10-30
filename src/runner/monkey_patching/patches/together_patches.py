from functools import wraps

from aco.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from aco.server.cache_manager import CACHE
from aco.common.logger import logger
from aco.runner.taint_wrappers import get_taint_origins, taint_wrap


# ===========================================================
# Patches for Together Client
# ===========================================================


def together_patch():
    try:
        from together import Together
    except ImportError:
        logger.info("Together not installed, skipping OpenAI patches")
        return

    def create_patched_init(original_init):

        @wraps(original_init)
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            patch_together_chat_completions_create(self.chat.completions)

        return patched_init

    Together.__init__ = create_patched_init(Together.__init__)


def patch_together_chat_completions_create(completions):
    try:
        from together.resources.chat.completions import ChatCompletions
    except ImportError:
        return

    # Original together.resources.chat.completions.ChatCompletions.create
    original_function = completions.create

    # Patched function (executed instead of together.resources.chat.completions.ChatCompletions.create)
    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "together.resources.chat.completions.ChatCompletions.create"

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
    completions.create = patched_function.__get__(completions, ChatCompletions)
