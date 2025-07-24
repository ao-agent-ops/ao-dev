import importlib
import os
import yaml

from common.logger import logger
from common.utils import rel_path_to_abs
from runtime_tracing.monkey_patches import no_notify_patch, notify_server_patch, CUSTOM_PATCH_FUNCTIONS


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

def _import_from_qualified_name(qualified_name):
    """Import a function or method from a fully qualified name."""
    parts = qualified_name.split('.')
    module_path = '.'.join(parts[:-1])
    attr_path = parts[-1]
    module = importlib.import_module(module_path)
    # Support class methods: e.g., some.module.Class.method
    obj = module
    for part in parts[len(module_path.split('.')):]:
        obj = getattr(obj, part)
    return obj, module, parts

def apply_all_monkey_patches(server_conn):
    """
    Apply all monkey patches as specified in the YAML config and custom patch list.
    This includes generic patches (from YAML) and custom patch functions.
    """
    # 1. Apply generic patches from YAML config
    # config_path = rel_path_to_abs(__file__, config_path)
    # with open(config_path, "r") as f:
    #     config = yaml.safe_load(f)
    # cached_functions = config.get("cached_functions") or []
    # for qualified_name in cached_functions:
    #     func, module, parts = _import_from_qualified_name(qualified_name)
    #     # Patch the function/method in its parent (module or class)
    #     parent = module
    #     if len(parts) > 1:
    #         # If it's a class method, get the class
    #         for part in parts[1:-1]:
    #             parent = getattr(parent, part)
    #     setattr(parent, parts[-1], no_notify_patch(func))

    # 2. Apply custom patches (these handle their own logic and server notification)
    for patch_func in CUSTOM_PATCH_FUNCTIONS:
        patch_func(server_conn)

if __name__ == "__main__":
    yaml_path = rel_path_to_abs(__file__,"agent-copilot/configs/cache.yaml")
    apply_all_monkey_patches(None)
