import json
from typing import Any, Dict, List, Tuple
from aco.runner.monkey_patching.api_parsers.openai_api_parser import (
    func_kwargs_to_json_str_openai,
    api_obj_to_json_str_openai,
    json_str_to_api_obj_openai,
    get_model_openai,
)
from aco.runner.monkey_patching.api_parsers.anthropic_api_parser import (
    func_kwargs_to_json_str_anthropic,
    api_obj_to_json_str_anthropic,
    json_str_to_api_obj_anthropic,
    get_model_anthropic,
)
from aco.runner.monkey_patching.api_parsers.google_api_parser import (
    func_kwargs_to_json_str_google,
    api_obj_to_json_str_google,
    json_str_to_api_obj_google,
    get_model_google,
)
from aco.runner.monkey_patching.api_parsers.mcp_api_parser import (
    func_kwargs_to_json_str_mcp,
    api_obj_to_json_str_mcp,
    json_str_to_api_obj_mcp,
    json_str_to_original_inp_dict_mcp,
    get_model_mcp,
)


def json_str_to_original_inp_dict(json_str: str, input_dict: dict, api_type: str) -> dict:
    if api_type == "MCP.ClientSession.send_request":
        return json_str_to_original_inp_dict_mcp(json_str, input_dict)
    else:
        return json.loads(json_str)


def func_kwargs_to_json_str(input_dict: Dict[str, Any], api_type: str) -> Tuple[str, List[str]]:
    if api_type in [
        "OpenAI.chat.completions.create",
        "AsyncOpenAI.chat.completions.create",
        "OpenAI.responses.create",
        "AsyncOpenAI.responses.create",
    ]:
        return func_kwargs_to_json_str_openai(input_dict, api_type)
    elif api_type == "Anthropic.messages.create":
        return func_kwargs_to_json_str_anthropic(input_dict)
    elif api_type in [
        "google.genai.models._api_client.request",
        "google.genai.models._api_client.request_streamed",
    ]:
        return func_kwargs_to_json_str_google(input_dict)
    elif api_type == "MCP.ClientSession.send_request":
        return func_kwargs_to_json_str_mcp(input_dict)
    else:
        raise ValueError(f"Unknown API type {api_type}")


def api_obj_to_json_str(response_obj: Any, api_type: str) -> str:
    if api_type in [
        "OpenAI.chat.completions.create",
        "AsyncOpenAI.chat.completions.create",
        "OpenAI.responses.create",
        "AsyncOpenAI.responses.create",
    ]:
        return api_obj_to_json_str_openai(response_obj)
    elif api_type == "Anthropic.messages.create":
        return api_obj_to_json_str_anthropic(response_obj)
    elif api_type in [
        "google.genai.models._api_client.request",
        "google.genai.models._api_client.request_streamed",
    ]:
        return api_obj_to_json_str_google(response_obj)
    elif api_type == "MCP.ClientSession.send_request":
        return api_obj_to_json_str_mcp(response_obj)
    else:
        raise ValueError(f"Unknown API type {api_type}")


def json_str_to_api_obj(new_output_text: str, api_type: str) -> Any:
    if api_type in [
        "OpenAI.chat.completions.create",
        "AsyncOpenAI.chat.completions.create",
        "OpenAI.responses.create",
        "AsyncOpenAI.responses.create",
    ]:
        return json_str_to_api_obj_openai(new_output_text, api_type)
    elif api_type == "Anthropic.messages.create":
        return json_str_to_api_obj_anthropic(new_output_text)
    elif api_type in [
        "google.genai.models._api_client.request",
        "google.genai.models._api_client.request_streamed",
    ]:
        return json_str_to_api_obj_google(new_output_text)
    elif api_type == "MCP.ClientSession.send_request":
        return json_str_to_api_obj_mcp(new_output_text)
    else:
        raise ValueError(f"Unknown API type {api_type}")


def get_model_name(input_dict: Dict[str, Any], api_type: str) -> str:
    if api_type in [
        "OpenAI.chat.completions.create",
        "AsyncOpenAI.chat.completions.create",
        "OpenAI.responses.create",
        "AsyncOpenAI.responses.create",
    ]:
        return get_model_openai(input_dict)
    elif api_type == "Anthropic.messages.create":
        return get_model_anthropic(input_dict)
    elif api_type in [
        "google.genai.models._api_client.request",
        "google.genai.models._api_client.request_streamed",
    ]:
        return get_model_google(input_dict)
    elif api_type == "MCP.ClientSession.send_request":
        return get_model_mcp(input_dict)
    else:
        raise ValueError(f"Unknown API type {api_type}")
