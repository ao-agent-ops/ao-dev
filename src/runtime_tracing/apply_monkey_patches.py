import importlib
from runtime_tracing.utils import (
    no_notify_patch,
    notify_server_patch,
)

from runtime_tracing.monkey_patches.openai_patches import openai_patch, async_openai_patch
from runtime_tracing.monkey_patches.anthropic_patches import anthropic_patch
from runtime_tracing.monkey_patches.vertexai_patches import vertexai_patch


def patch_by_path(dotted_path, *, notify=False):
    """
    Import the module+attr from `dotted_path`, wrap it with no_notify_patch,
    and re-assign it in-place. Returns the original function.
    """
    module_path, attr = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    original = getattr(module, attr)

    if notify:
        wrapped = notify_server_patch(original)
    else:
        wrapped = no_notify_patch(original)

    setattr(module, attr, wrapped)
    return original


def _import_from_qualified_name(qualified_name):
    """Import a function or method from a fully qualified name."""
    parts = qualified_name.split(".")
    module_path = ".".join(parts[:-1])
    module = importlib.import_module(module_path)
    # Support class methods: e.g., some.module.Class.method
    obj = module
    for part in parts[len(module_path.split(".")) :]:
        obj = getattr(obj, part)
    return obj, module, parts


def apply_all_monkey_patches():
    """
    Apply all monkey patches as specified in the YAML config and custom patch list.
    This includes generic patches (from YAML) and custom patch functions.
    """
    # 1. Apply generic patches from YAML config
    # TODO cached_functions used to be in config.yaml but not anymore.
    # not sure how this example should run.
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
        patch_func()


# ===========================================================
# Patch function registry
# ===========================================================

# Subclient patch functions (e.g., patch_OpenAI.responses.create)
# are NOT included here and should only be called from within the OpenAI.__init__ patch.

CUSTOM_PATCH_FUNCTIONS = [
    openai_patch,
    async_openai_patch,
    anthropic_patch,
    vertexai_patch,
]
