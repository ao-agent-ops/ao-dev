import importlib
import os

import yaml

from common.logging_config import setup_logging
from common.utils import rel_path_to_abs
from runtime_tracing.monkey_patches import no_notify_patch, notify_server_patch
logger = setup_logging()


def patch_by_path(dotted_path, *, notify=False, server_conn=None):
    """
    Import the module+attr from `dotted_path`, wrap it with no_notify_patch,
    and re-assign it in-place. Returns the original function.
    """
    module_path, attr = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    original = getattr(module, attr)

    if notify:
        wrapped = notify_server_patch(original, server_conn)
    else:
        wrapped = no_notify_patch(original)

    setattr(module, attr, wrapped)
    return original


def apply_all_monkey_patches(yaml_path=None):
    # TODO: For debugging:
    dir = os.path.dirname(__file__)
    yaml_path = "agent-copilot/testbed/try_out_repo/.user_config/cache.yaml"

    # Read functions that should be patched.
    with open(yaml_path, 'r') as f:
        functions = yaml.safe_load(f)["cached_functions"]
    
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
                patch_by_path(fn, notify=False, server_conn=None)
            except ImportError:
                logger.warning(f"Couldn't import {fn}, calls will not be cached.")
            except ValueError:
                logger.warning(f"`{fn}` has invalid format, calls will not be cached.")


if __name__ == "__main__":
    yaml_path = rel_path_to_abs(__file__,"agent-copilot/configs/cache.yaml")
    apply_all_monkey_patches(yaml_path)
