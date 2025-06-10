import importlib

import yaml

from common.logging_config import setup_logging
from runtime_tracing.monkey_patches import no_notify_patch, notify_server_patch
logger = setup_logging()

def patch_by_path(dotted_path, *, input=None, output=None, notify=False, server_conn=None):
    """
    Import the module+attr from `dotted_path`, wrap it with no_notify_patch,
    and re-assign it in-place. Returns the original function.
    """
    module_path, attr = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    original = getattr(module, attr)
    if notify:
        assert server_conn is not None
        wrapped = notify_server_patch(original, server_conn, input=input, output=output)
    else:
        wrapped = no_notify_patch(original, input=input, output=output)
    setattr(module, attr, wrapped)
    return original


def apply_all_monkey_patches(yaml_path=None):
    # TODO: For debugging:
    yaml_path = "/Users/ferdi/Documents/agent-copilot/testbed/code_repos/try_out/.user_config/cache.yaml"


    # Read functions that should be patched.
    with open(yaml_path, 'r') as f:
        functions = yaml.safe_load(f)
    
    # Patch.
    for fn in functions:
        if fn == "":
            pass
        elif fn == "":
            pass
        elif fn == "":
            pass
        else:
            try:
                patch_by_path(fn, input=None, output="hello from patch :)", notify=False, server_conn=None)
            except ImportError:
                logger.warning(f"Couldn't import {fn}, calls will not be cached.")
            except ValueError:
                logger.warning(f"`{fn}` has invalid format, calls will not be cached.")


if __name__ == "__main__":
    yaml_path = "/Users/ferdi/Documents/agent-copilot/testbed/code_repos/try_out/.user_config/cache.yaml"
    apply_all_monkey_patches(yaml_path)
