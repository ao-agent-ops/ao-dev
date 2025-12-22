from ao.runner.monkey_patching.patches.mcp_patches import mcp_patch
from ao.runner.monkey_patching.patches.uuid_patches import uuid_patch

# from ao.runner.monkey_patching.patches.file_patches import apply_file_patches
from ao.runner.monkey_patching.patches.httpx_patch import httpx_patch
from ao.runner.monkey_patching.patches.requests_patch import requests_patch
from ao.runner.monkey_patching.patches.genai_patch import genai_patch


def apply_all_monkey_patches():
    """
    Apply all monkey patches as specified in the YAML config and custom patch list.
    This includes generic patches (from YAML) and custom patch functions.
    """
    for patch_func in CUSTOM_PATCH_FUNCTIONS:
        patch_func()


CUSTOM_PATCH_FUNCTIONS = [
    # str_patch removed - str.join now handled by AST rewriting + exec_func
    uuid_patch,
    # apply_file_patches,
    mcp_patch,
    httpx_patch,
    requests_patch,
    genai_patch,
]
