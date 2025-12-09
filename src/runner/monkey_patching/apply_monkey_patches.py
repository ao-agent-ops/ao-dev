from aco.runner.monkey_patching.patches.mcp_patches import mcp_patch
from aco.runner.monkey_patching.patches.openai_patches import openai_patch, async_openai_patch
from aco.runner.monkey_patching.patches.anthropic_patches import (
    anthropic_patch,
    async_anthropic_patch,
)
from aco.runner.monkey_patching.patches.google_genai_patches import google_genai_patch
from aco.runner.monkey_patching.patches.together_patches import together_patch
from aco.runner.monkey_patching.patches.uuid_patches import uuid_patch
from aco.runner.monkey_patching.patches.builtin_patches import str_patch
from aco.runner.monkey_patching.patches.file_patches import apply_file_patches
from aco.runner.monkey_patching.patches.httpx_patch import httpx_patch
from aco.runner.monkey_patching.patches.requests_patch import requests_patch


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
    uuid_patch,
    apply_file_patches,
    # openai_patch,
    # async_openai_patch,
    # together_patch,
    # anthropic_patch,
    # async_anthropic_patch,
    # google_genai_patch,
    mcp_patch,
    httpx_patch,
    requests_patch,
]
