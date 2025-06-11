import diskcache as dc

# TODO: Read config and init cache.
cache_dir = "/Users/ferdi/Documents/agent-copilot/testbed/code_repos/try_out/.user_config/"
size_limit = int(2e9)
TIME_TO_LIVE = None
CACHE = dc.Cache(cache_dir, size_limit=size_limit) # ".../.cache"
