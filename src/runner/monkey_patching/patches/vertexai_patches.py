from functools import wraps
from aco.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from aco.server.cache_manager import CACHE
from aco.common.logger import logger
from aco.runner.taint_wrappers import get_taint_origins, taint_wrap


def vertexai_patch():
    """
    Patch Vertex AI API to use persistent cache and edits.
    """
    try:
        from google import genai
    except ImportError:
        logger.info("Google GenAI not installed, skipping Vertex AI patches")
        return

    # Patch the Client.__init__ method to patch the models.generate_content method
    original_init = genai.Client.__init__

    @wraps(original_init)
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        patch_client_models_generate_content(self.models)

    genai.Client.__init__ = new_init


def patch_client_models_generate_content(models_instance):
    try:
        from google.genai.models import Models
    except ImportError:
        return

    original_function = models_instance.generate_content

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):
        # 1. Set API identifier to fully qualified name of patched function.
        api_type = "vertexai client_models_generate_content"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        # 4. Get result from cache or call LLM.
        input_to_use, result, node_id = CACHE.get_in_out(input_dict, api_type)
        if result is None:
            result = original_function(**input_to_use)
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
    models_instance.generate_content = patched_function.__get__(models_instance, Models)
