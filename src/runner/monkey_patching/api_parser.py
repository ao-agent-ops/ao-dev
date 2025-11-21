from typing import Any, Dict, List, Tuple
from aco.runner.monkey_patching.api_parsers.openai_api_parser import (
    _get_input_openai_chat_completions_create,
    _get_input_openai_responses_create,
    _set_input_openai_chat_completions_create,
    _set_input_openai_responses_create,
    _get_input_openai_beta_threads_create,
    _get_input_openai_beta_threads_create_and_poll,
    _set_input_openai_beta_threads_create,
    _get_output_openai_chat_completions_create,
    _get_output_openai_responses_create,
    _set_output_openai_chat_completions_create,
    _get_output_openai_beta_threads_create_and_poll,
    _set_output_openai_responses_create,
    _set_output_openai_beta_threads_create_and_poll,
    _get_model_openai_chat_completions_create,
    _get_model_openai_responses_create,
    _get_model_openai_beta_threads_create_and_poll,
    _get_model_openai_beta_threads_create,
)
from aco.runner.monkey_patching.api_parsers.anthropic_api_parser import (
    _get_input_anthropic_messages_create,
    _set_input_anthropic_messages_create,
    _get_output_anthropic_messages_create,
    _set_output_anthropic_messages_create,
    _get_model_anthropic_messages_create,
)
from aco.runner.monkey_patching.api_parsers.vertex_api_parser import (
    _get_input_vertex_client_models_generate_content,
    _set_input_vertex_client_models_generate_content,
    _get_output_vertex_client_models_generate_content,
    _set_output_vertex_client_models_generate_content,
    _get_model_vertex_client_models_generate_content,
)
from aco.runner.monkey_patching.api_parsers.together_parser import (
    _get_input_together_resources_chat_completions_ChatCompletions_create,
    _set_input_together_resources_chat_completions_ChatCompletions_create,
    _get_output_together_resources_chat_completions_ChatCompletions_create,
    _set_output_together_resources_chat_completions_ChatCompletions_create,
    _get_model_together_resources_chat_completions_ChatCompletions_create,
)
from aco.runner.monkey_patching.api_parsers.mcp_api_parser import (
    _get_input_mcp_client_session_call_tool,
    _set_input_mcp_client_session_call_tool,
    _get_output_mcp_client_session_call_tool,
    _set_output_mcp_client_session_call_tool,
    _get_model_mcp_client_session_call_tool,
)


def get_input(input_dict: Dict[str, Any], api_type: str) -> Tuple[str, List[str], List[str]]:
    """Extract input text, attachments, and tools from API input."""
    if api_type == "OpenAI.chat.completions.create":
        return _get_input_openai_chat_completions_create(input_dict)
    elif api_type == "AsyncOpenAI.chat.completions.create":
        return _get_input_openai_chat_completions_create(input_dict)
    elif api_type == "OpenAI.responses.create":
        return _get_input_openai_responses_create(input_dict)
    elif api_type == "AsyncOpenAI.responses.create":
        return _get_input_openai_responses_create(input_dict)
    elif api_type == "OpenAI.beta.threads.create":
        return _get_input_openai_beta_threads_create(input_dict)
    elif api_type == "OpenAI.beta.threads.create_and_poll":
        return _get_input_openai_beta_threads_create_and_poll(input_dict)
    elif api_type == "Anthropic.messages.create":
        return _get_input_anthropic_messages_create(input_dict)
    elif api_type == "vertexai client_models_generate_content":
        return _get_input_vertex_client_models_generate_content(input_dict)
    elif api_type == "together.resources.chat.completions.ChatCompletions.create":
        return _get_input_together_resources_chat_completions_ChatCompletions_create(input_dict)
    elif api_type == "MCP.ClientSession.call_tool":
        return _get_input_mcp_client_session_call_tool(input_dict)
    else:
        raise ValueError(f"Unknown API type {api_type}")


def set_input(input_dict: Dict[str, Any], new_input_text: str, api_type: str) -> None:
    """Returns pickle with changed input text."""
    if api_type == "OpenAI.chat.completions.create":
        return _set_input_openai_chat_completions_create(input_dict, new_input_text)
    elif api_type == "AsyncOpenAI.chat.completions.create":
        return _set_input_openai_chat_completions_create(input_dict, new_input_text)
    elif api_type == "OpenAI.responses.create":
        return _set_input_openai_responses_create(input_dict, new_input_text)
    elif api_type == "AsyncOpenAI.responses.create":
        return _set_input_openai_responses_create(input_dict, new_input_text)
    elif api_type == "OpenAI.beta.threads.create":
        return _set_input_openai_beta_threads_create(input_dict, new_input_text)
    elif api_type == "Anthropic.messages.create":
        return _set_input_anthropic_messages_create(input_dict, new_input_text)
    elif api_type == "vertexai client_models_generate_content":
        return _set_input_vertex_client_models_generate_content(input_dict, new_input_text)
    elif api_type == "together.resources.chat.completions.ChatCompletions.create":
        return _set_input_together_resources_chat_completions_ChatCompletions_create(
            input_dict, new_input_text
        )
    elif api_type == "MCP.ClientSession.call_tool":
        return _set_input_mcp_client_session_call_tool(input_dict, new_input_text)
    else:
        raise ValueError(f"Unknown API type {api_type}")


def get_output(response_obj: Any, api_type: str) -> str:
    if api_type == "OpenAI.chat.completions.create":
        return _get_output_openai_chat_completions_create(response_obj)
    elif api_type == "AsyncOpenAI.chat.completions.create":
        return _get_output_openai_chat_completions_create(response_obj)
    elif api_type == "OpenAI.responses.create":
        return _get_output_openai_responses_create(response_obj)
    elif api_type == "AsyncOpenAI.responses.create":
        return _get_output_openai_responses_create(response_obj)
    elif api_type == "OpenAI.beta.threads.create_and_poll":
        return _get_output_openai_beta_threads_create_and_poll(response_obj)
    elif api_type == "Anthropic.messages.create":
        return _get_output_anthropic_messages_create(response_obj)
    elif api_type == "vertexai client_models_generate_content":
        return _get_output_vertex_client_models_generate_content(response_obj)
    elif api_type == "together.resources.chat.completions.ChatCompletions.create":
        return _get_output_together_resources_chat_completions_ChatCompletions_create(response_obj)
    elif api_type == "MCP.ClientSession.call_tool":
        return _get_output_mcp_client_session_call_tool(response_obj)
    else:
        raise ValueError(f"Unknown API type {api_type}")


def set_output(original_output_obj: Any, new_output_text: str, api_type):
    if api_type == "OpenAI.chat.completions.create":
        return _set_output_openai_chat_completions_create(original_output_obj, new_output_text)
    elif api_type == "AsyncOpenAI.chat.completions.create":
        return _set_output_openai_chat_completions_create(original_output_obj, new_output_text)
    elif api_type == "OpenAI.responses.create":
        return _set_output_openai_responses_create(original_output_obj, new_output_text)
    elif api_type == "AsyncOpenAI.responses.create":
        return _set_output_openai_responses_create(original_output_obj, new_output_text)
    elif api_type == "OpenAI.beta.threads.create_and_poll":
        return _set_output_openai_beta_threads_create_and_poll(original_output_obj, new_output_text)
    elif api_type == "Anthropic.messages.create":
        return _set_output_anthropic_messages_create(original_output_obj, new_output_text)
    elif api_type == "vertexai client_models_generate_content":
        return _set_output_vertex_client_models_generate_content(
            original_output_obj, new_output_text
        )
    elif api_type == "together.resources.chat.completions.ChatCompletions.create":
        return _set_output_together_resources_chat_completions_ChatCompletions_create(
            original_output_obj, new_output_text
        )
    elif api_type == "MCP.ClientSession.call_tool":
        return _set_output_mcp_client_session_call_tool(original_output_obj, new_output_text)
    else:
        raise ValueError(f"Unknown API type {api_type}")


def get_model_name(input_dict: Dict[str, Any], api_type: str) -> str:
    if api_type == "OpenAI.chat.completions.create":
        return _get_model_openai_chat_completions_create(input_dict)
    elif api_type == "AsyncOpenAI.chat.completions.create":
        return _get_model_openai_chat_completions_create(input_dict)
    elif api_type == "OpenAI.responses.create":
        return _get_model_openai_responses_create(input_dict)
    elif api_type == "AsyncOpenAI.responses.create":
        return _get_model_openai_responses_create(input_dict)
    elif api_type == "OpenAI.beta.threads.create_and_poll":
        return _get_model_openai_beta_threads_create_and_poll(input_dict)
    elif api_type == "OpenAI.beta.threads.create":
        return _get_model_openai_beta_threads_create(input_dict)
    elif api_type == "Anthropic.messages.create":
        return _get_model_anthropic_messages_create(input_dict)
    elif api_type == "vertexai client_models_generate_content":
        return _get_model_vertex_client_models_generate_content(input_dict)
    elif api_type == "together.resources.chat.completions.ChatCompletions.create":
        return _get_model_together_resources_chat_completions_ChatCompletions_create(input_dict)
    elif api_type == "MCP.ClientSession.call_tool":
        return _get_model_mcp_client_session_call_tool(input_dict)
    else:
        raise ValueError(f"Unknown API type {api_type}")
