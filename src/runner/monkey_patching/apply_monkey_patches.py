import importlib
from aco.runner.monkey_patching.patching_utils import (
    no_notify_patch,
    notify_server_patch,
)

from aco.runner.monkey_patching.patches.openai_patches import openai_patch, async_openai_patch
from aco.runner.monkey_patching.patches.anthropic_patches import anthropic_patch
from aco.runner.monkey_patching.patches.vertexai_patches import vertexai_patch
from aco.runner.monkey_patching.patches.uuid_patches import uuid_patch
from aco.runner.monkey_patching.patches.builtin_patches import str_patch
from aco.runner.monkey_patching.patches.file_patches import apply_file_patches


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


def apply_all_monkey_patches():
    """
    Apply all monkey patches as specified in the YAML config and custom patch list.
    This includes generic patches (from YAML) and custom patch functions.
    """
    for patch_func in CUSTOM_PATCH_FUNCTIONS:
        patch_func()


# ===========================================================
# Patch function registry
# ===========================================================

# Subclient patch functions (e.g., patch_OpenAI.responses.create)
# are NOT included here and should only be called from within the OpenAI.__init__ patch.

CUSTOM_PATCH_FUNCTIONS = [
    str_patch,
    # uuid_patch,
    apply_file_patches,
    openai_patch,
    async_openai_patch,
    anthropic_patch,
    vertexai_patch,
]
