from functools import wraps
from aco.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from aco.server.database_manager import DB
from aco.common.logger import logger
from aco.common.utils import is_whitelisted_endpoint
from aco.runner.taint_wrappers import get_taint_origins, taint_wrap


def requests_patch():
    try:
        from requests import Session
    except ImportError:
        logger.info("requests not installed, skipping requests patches")
        return

    def create_patched_init(original_init):

        @wraps(original_init)
        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            patch_requests_send(self, type(self))

        return patched_init

    Session.__init__ = create_patched_init(Session.__init__)


def patch_requests_send(bound_obj, bound_cls):
    # bound_obj has a send method, which we are patching
    original_function = bound_obj.send

    @wraps(original_function)
    def patched_function(self, *args, **kwargs):

        api_type = "requests.Session.send"

        # 2. Get full input dict.
        input_dict = get_input_dict(original_function, *args, **kwargs)

        # 3. Get taint origins (did another LLM produce the input?).
        taint_origins = get_taint_origins(input_dict)

        if not is_whitelisted_endpoint(input_dict["request"].path_url):
            result = original_function(*args, **kwargs)
            return taint_wrap(result, taint_origins)

        # 4. Get result from cache or call LLM.
        cache_output = DB.get_in_out(input_dict, api_type)
        if cache_output.output is None:
            result = original_function(**cache_output.input_dict)  # Call LLM.
            DB.cache_output(cache_result=cache_output, output_obj=result, api_type=api_type)

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

    bound_obj.send = patched_function.__get__(bound_obj, bound_cls)
