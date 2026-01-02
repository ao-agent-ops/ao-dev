from functools import wraps
from ao.runner.monkey_patching.patching_utils import get_input_dict, send_graph_node_and_edges
from ao.server.database_manager import DB
from ao.common.utils import is_whitelisted_endpoint
import builtins


def requests_patch():
    try:
        from requests import Session
    except ImportError:
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

        # 3. Get taint origins from ACTIVE_TAINT (set by exec_func)
        taint_origins = list(builtins.ACTIVE_TAINT.get())

        if not is_whitelisted_endpoint(input_dict["request"].path_url):
            result = original_function(*args, **kwargs)
            return result  # No wrapping here, exec_func will use existing escrow

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

        # 6. Set the new taint in escrow for exec_func to wrap with.
        builtins.ACTIVE_TAINT.set([cache_output.node_id])
        return cache_output.output  # No wrapping here, exec_func will wrap

    bound_obj.send = patched_function.__get__(bound_obj, bound_cls)
