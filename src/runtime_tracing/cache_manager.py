import hashlib
import pickle
import diskcache as dc
import yaml

from common.utils import rel_path_to_abs


def cache_key(fn, args, kwargs):
    context = (
        fn.__module__, 
        fn.__name__,
        args,
        tuple(sorted(kwargs.items())),
    )
    raw = pickle.dumps(context)
    return hashlib.sha256(raw).hexdigest()


class CacheManager:
    """
    Chec if input / outputs to an LLM call are overwritten.
    Check if outputs of a function are cached.

    get_input, get_output return None if no special inputs/outputs should be used
    """
    def __init__(self):
        config_path = rel_path_to_abs(__file__, "agent-copilot/configs/cache.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)["cache_config"]

        # cache_dir = rel_path_to_abs(__file__, config["cache_location"])
        size_limit = config["size_limit"]
        ttl = config["time_to_live"]
        self.ttl = None if ttl == -1 else ttl
        self.cache = dc.Cache(size_limit=size_limit)

        self.input_overwrites = {} # "file:line_no" -> string
        self.output_overwrites = {} # "file:line_no" -> string


    def get_output(self, file_name, line_no, fn, args, kwargs):
        # Check if output overwritten.
        caller_id = f"{file_name}:{line_no}"
        if caller_id in self.output_overwrites:
            return self.output_overwrites[caller_id]
        
        # Check if output cached.
        key = cache_key(fn, args, kwargs)
        return self.cache.get(key, None)


    def get_input(self, file_name, line_no):
        caller_id = f"{file_name}:{line_no}"
        return self.input_overwrites.get(caller_id, None)


    def cache_output(self, result, file_name, line_no, fn, args, kwargs):
        key = cache_key(fn, args, kwargs)
        self.cache.set(key, result, expire=self.ttl, tag=f"{file_name}:{line_no}")


    def evict_caller(self, file_name, line_no):
        # TODO: I don't think we ever need this?
        caller_id = f"{file_name}:{line_no}"
        self.cache.evict(caller_id)


    def add_input_overwrite(self, file_name, line_no, prompt):
        # NOTE: Assuming only prompt strings are cached.
        caller_id = f"{file_name}:{line_no}"
        self.input_overwrites[caller_id] = prompt


    def add_output_overwrite(self, file_name, line_no, prompt):
        # NOTE: Assuming only prompt strings are cached.
        caller_id = f"{file_name}:{line_no}"
        self.output_overwrites[caller_id] = prompt


    def remove_input_overwrite(self, file_name, line_no):
        caller_id = f"{file_name}:{line_no}"
        del self.input_overwrites[caller_id]


    def remove_output_overwrite(self, file_name, line_no):
        caller_id = f"{file_name}:{line_no}"
        del self.output_overwrites[caller_id]



CACHE = CacheManager()
