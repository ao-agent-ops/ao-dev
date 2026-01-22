"""
Langchain API parser for tool serialization.

This module handles serialization of langchain tool inputs/outputs for
display in the UI. Only tool-related functions are needed since LLM calls
go through httpx and use its serialization.
"""

import json
from typing import Any, Dict, List, Tuple


def func_kwargs_to_json_str_langchain(input_dict: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    Convert langchain tool invocation kwargs to JSON string.

    Args:
        input_dict: Contains 'tool_name' and 'input' from BaseTool.invoke

    Returns:
        Tuple of (JSON string, list of attachment IDs)
    """
    tool_input = input_dict.get("input")
    if hasattr(tool_input, "model_dump"):
        serialized_input = tool_input.model_dump(mode="json")
    elif hasattr(tool_input, "dict"):
        serialized_input = tool_input.dict()
    elif isinstance(tool_input, dict):
        serialized_input = tool_input
    elif isinstance(tool_input, str):
        serialized_input = tool_input
    else:
        serialized_input = str(tool_input)

    result = {
        "tool_name": input_dict.get("tool_name", "unknown_tool"),
        "input": serialized_input,
    }

    return json.dumps(result, sort_keys=True, default=str), []


def api_obj_to_json_str_langchain(obj: Any) -> str:
    """
    Convert langchain tool output to JSON string.

    Args:
        obj: The tool's return value

    Returns:
        JSON string representation
    """
    if hasattr(obj, "model_dump"):
        output_dict = obj.model_dump(mode="json")
    elif hasattr(obj, "dict"):
        output_dict = obj.dict()
    elif isinstance(obj, dict):
        output_dict = obj
    elif isinstance(obj, (list, tuple)):
        output_dict = {"result": list(obj)}
    elif isinstance(obj, str):
        output_dict = {"result": obj}
    else:
        output_dict = {"result": str(obj)}

    return json.dumps(output_dict, sort_keys=True, default=str)


def json_str_to_api_obj_langchain(json_str: str) -> Any:
    """
    Convert JSON string back to a tool output object.

    Args:
        json_str: JSON string from cache

    Returns:
        The parsed output (dict with 'result' key or the original structure)
    """
    output_dict = json.loads(json_str)

    if isinstance(output_dict, dict) and list(output_dict.keys()) == ["result"]:
        return output_dict["result"]

    return output_dict


def json_str_to_original_inp_dict_langchain(json_str: str, input_dict: dict) -> dict:
    """
    Apply edited input back to the original input_dict structure.

    Args:
        json_str: Edited JSON string from UI
        input_dict: Original input dict with 'tool_name' and 'input'

    Returns:
        Updated input_dict with modified input
    """
    edited = json.loads(json_str)
    input_dict["input"] = edited.get("input", input_dict.get("input"))
    return input_dict
