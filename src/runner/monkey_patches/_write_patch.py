import asyncio
from runner.monkey_patches._generate_patch_helpers import (
    _1_get_input,
    _2_set_input,
    _3_get_output,
    _4_set_output,
    _5_install_set_and_get,
    extract_tag_content,
)
from runner.utils import get_input_dict


# =================================================
# Define which function to patch.
# =================================================
# TODO: Store original function (you may include "set up" code like client creation).
from together import Together

client = Together()
function_to_patch = client.chat.completions.create

# =================================================


def _log_patch(*args, **kwargs):
    full_dict = get_input_dict(function_to_patch, *args, **kwargs)
    input_dict = full_dict
    result = function_to_patch(*args, **kwargs)
    result_obj = result
    return input_dict, result_obj


client.chat.completions.create = _log_patch  # <-- TODO: Replace original function to patch
input_dict, result_obj = response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": "What are some fun things to do in New York?"}],
)  # <-- TODO: Call

# =================================================
# Automatic patch creation
# =================================================


def _get_function_id(function_to_patch):
    module_name = function_to_patch.__module__
    qualname_parts = function_to_patch.__qualname__.split(".")
    last_two_parts = (
        ".".join(qualname_parts[-2:])
        if len(qualname_parts) >= 2
        else function_to_patch.__qualname__
    )
    dotted_id = f"{module_name}.{last_two_parts}"
    return dotted_id.replace(".", "_")


def get_api_type(function_to_patch):
    return f"{function_to_patch.__module__}.{function_to_patch.__qualname__}"


# 1. Get input.
# function_id = _get_function_id(function_to_patch)
# get_input = _1_get_input(input_dict, function_id)
# get_input = extract_tag_content(get_input).get("implementation", "unavailable")

# # 2. Set input.
# set_input =_2_set_input(input_dict, function_id)
# set_input = extract_tag_content(set_input).get("implementation", "unavailable")

# # 3. Get output.
# get_output = _3_get_output(result_obj, function_id)
# get_output = extract_tag_content(get_output).get("implementation", "unavailable")

# # 4. Set output.
# set_output = _4_set_output(result_obj, function_id)
# set_output = extract_tag_content(set_output).get("implementation", "unavailable")

# 5. Install set and get.
get_input = None
set_input = None
get_output = None
set_output = None
api_type = get_api_type(function_to_patch)
asyncio.run(_5_install_set_and_get(api_type, get_input, set_input, get_output, set_output))

print("✅ Wrote getters and setters.")

# 6. Write patch.

# 7. Install patch.

# 8. Write test

# 9. Run test
# TODO: pytest.
