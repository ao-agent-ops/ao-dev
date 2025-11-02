import os
from typing import Any, Dict, List, Tuple

"""
TODO: Should add some fallbacks for robustness ...

try:
    return input_obj.model
except:
    return "unknown"
"""


# ===============================================
# OpenAI.chat.completions.create
# ===============================================


def _get_input_openai_chat_completions_create(
    input_dict: Dict[str, Any],
) -> Tuple[str, List[str], List[str]]:
    """Extract input text, attachments, and tools from OpenAI chat completions input."""
    messages = input_dict.get("messages", [])
    if not messages:
        return str(input_dict), [], []

    # Get the last user message as the primary input
    last_message = messages[-1]

    # Extract content as string based on message type using role field
    if last_message.get("role") == "developer":
        # content can be str or Iterable[ChatCompletionContentPartTextParam]
        content_value = last_message.get("content", "")
        if isinstance(content_value, str):
            content = content_value
        elif hasattr(content_value, "__iter__") and not isinstance(content_value, str):
            text_parts = []
            for part in content_value:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            content = " ".join(text_parts)
        else:
            content = str(content_value)

    elif last_message.get("role") == "system":
        # content can be str or Iterable[ChatCompletionContentPartTextParam]
        content_value = last_message.get("content", "")
        if isinstance(content_value, str):
            content = content_value
        elif hasattr(content_value, "__iter__") and not isinstance(content_value, str):
            text_parts = []
            for part in content_value:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            content = " ".join(text_parts)
        else:
            content = str(content_value)

    elif last_message.get("role") == "user":
        # content can be str or Iterable[ChatCompletionContentPartParam]
        content_value = last_message.get("content", "")
        if isinstance(content_value, str):
            content = content_value
        elif hasattr(content_value, "__iter__") and not isinstance(content_value, str):
            text_parts = []
            for part in content_value:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif part.get("type") == "image":
                        text_parts.append("[Image]")
                    elif part.get("type") == "input_audio":
                        text_parts.append("[Audio]")
                    elif part.get("type") == "file":
                        file_info = part.get("file", {})
                        filename = file_info.get("filename", "file")
                        text_parts.append(f"[File: {filename}]")
            content = " ".join(text_parts) if text_parts else str(content_value)
        else:
            content = str(content_value)

    elif last_message.get("role") == "assistant":
        # content can be str, Iterable[ContentArrayOfContentPart], or None
        content_value = last_message.get("content")
        if isinstance(content_value, str):
            content = content_value
        elif content_value is None:
            # Check for function_call or tool_calls as fallback
            if last_message.get("function_call"):
                func_call = last_message.get("function_call", {})
                content = f"Function call: {func_call.get('name', 'unknown')} with args: {func_call.get('arguments', '')}"
            elif last_message.get("tool_calls"):
                tool_calls = last_message.get("tool_calls", [])
                call_descriptions = []
                for tool_call in tool_calls:
                    if hasattr(tool_call, "function") and hasattr(tool_call.function, "name"):
                        call_descriptions.append(f"{tool_call.function.name}")
                    elif isinstance(tool_call, dict) and "function" in tool_call:
                        call_descriptions.append(f"{tool_call['function'].get('name', 'unknown')}")
                content = f"Tool calls: {', '.join(call_descriptions)}" if call_descriptions else ""
            else:
                content = ""
        elif hasattr(content_value, "__iter__") and not isinstance(content_value, str):
            text_parts = []
            for part in content_value:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                    elif part.get("type") == "refusal":
                        text_parts.append(part.get("refusal", ""))
            content = " ".join(text_parts) if text_parts else str(content_value)
        else:
            content = str(content_value)

    elif last_message.get("role") == "tool":
        # content can be str or Iterable[ChatCompletionContentPartTextParam]
        content_value = last_message.get("content", "")
        if isinstance(content_value, str):
            content = content_value
        elif hasattr(content_value, "__iter__") and not isinstance(content_value, str):
            text_parts = []
            for part in content_value:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            content = " ".join(text_parts)
        else:
            content = str(content_value)

    elif last_message.get("role") == "function":
        # content is Optional[str]
        content_value = last_message.get("content")
        if content_value is None:
            content = ""
        elif isinstance(content_value, str):
            content = content_value
        else:
            content = str(content_value)

    else:
        # Fallback for unknown message types
        content = str(last_message.get("content", ""))

    # For now, no attachment support in chat completions
    return content, [], []


def _set_input_openai_chat_completions_create(
    oritinal_input_dict: Dict[str, Any], new_input_text: bytes
) -> None:
    """Set new input text in OpenAI chat completions input."""
    oritinal_input_dict["messages"][-1]["content"] = new_input_text


def _get_output_openai_chat_completions_create(response_obj: Any) -> str:
    """Extract output text from OpenAI chat completions response."""
    if hasattr(response_obj, "choices") and response_obj.choices:
        choice = response_obj.choices[0]
        if hasattr(choice, "message") and hasattr(choice.message, "content"):
            return choice.message.content or ""
    return str(response_obj)


def _set_output_openai_chat_completions_create(original_output_obj: Any, output_text: str) -> None:
    """Set new output text in OpenAI chat completions response."""
    if hasattr(original_output_obj, "choices") and original_output_obj.choices:
        choice = original_output_obj.choices[0]
        if hasattr(choice, "message"):
            choice.message.content = output_text


def _get_model_openai_chat_completions_create(input_dict: Dict[str, Any]) -> str:
    """Extract model name from OpenAI chat completions input."""
    return input_dict.get("model", "unknown")


# ===============================================
# OpenAI.responses.create
# ===============================================


def _get_input_openai_responses_create(
    input_dict: Dict[str, Any],
) -> Tuple[str, List[str], List[str]]:
    """Extract input text, attachments, and tools from OpenAI responses create input."""
    input_data = input_dict.get("input", [])

    # Extract tools from the input_dict
    tools = input_dict.get("tools", [])
    tool_names = []

    if isinstance(tools, list):
        for tool in tools:
            if isinstance(tool, dict):
                tool_names.append(tool.get("name", "unknown_tool"))
            elif hasattr(tool, "name"):
                tool_names.append(tool.name)
            else:
                tool_names.append(str(tool))
        tool_names = sorted(tool_names)  # Sort for consistent cache keys
    else:
        tool_names = []

    if not input_data:
        return str(input_data), [], tool_names

    # Handle different input formats
    if isinstance(input_data, list):
        # Find the first user message and return only that
        for item in input_data:
            if isinstance(item, dict) and item.get("role") == "user" and "content" in item:
                return str(item["content"]), [], tool_names

        # Fallback: if no user message found, try to extract any content
        for item in input_data:
            if isinstance(item, dict) and "content" in item:
                return str(item["content"]), [], tool_names

        # Last resort: return first item as string
        if input_data:
            return str(input_data[0]), [], tool_names
        return str(input_data), [], tool_names
    else:
        return str(input_data), [], tool_names


def _set_input_openai_responses_create(
    original_input_dict: Dict[str, Any], new_input_text: str
) -> None:
    original_input_dict["input"] = new_input_text


def _get_output_openai_responses_create(response_obj: Any) -> str:
    last_output = response_obj.output[-1]
    if hasattr(last_output, "name"):
        # ResponseFunctionToolCall
        return last_output.name
    else:
        # ResponseOutputMessage
        output_text = last_output.content[-1].text
        return output_text


def _set_output_openai_responses_create(original_output_obj: Any, output_text: str) -> None:
    original_output_obj.output[-1].content[-1].text = output_text


def _get_model_openai_responses_create(input_dict: Dict[str, Any]) -> str:
    return input_dict.get("model", "unknown")


# ===============================================
# OpenAI.beta.threads.create (OpenAI assistants)
# ===============================================


def _get_input_openai_beta_threads_create_and_poll(
    input_obj: Any,
) -> Tuple[str, List[str], List[str]]:
    from aco.server.cache_manager import CACHE

    # Get paths to cached attachments.
    message = input_obj.content[-1].text.value
    attachments = [attachment.file_id for attachment in input_obj.attachments]
    attachments = CACHE.attachment_ids_to_paths(attachments)
    # Convert into format [(name, path), ...]
    attachments = [[os.path.basename(path), path] for path in attachments]
    return message, attachments, []


def _get_input_openai_beta_threads_create(
    input_dict: Dict[str, Any],
) -> Tuple[str, List[str], List[str]]:
    from aco.server.cache_manager import CACHE

    # Get paths to cached attachments.
    message = input_dict["messages"][-1]
    prompt = message["content"]
    attachments = []
    if "attachments" in message:
        attachments = [attachment["file_id"] for attachment in message["attachments"]]
    attachments = CACHE.attachment_ids_to_paths(attachments)
    # Convert into format [(name, path), ...]
    attachments = [[os.path.basename(path), path] for path in attachments]
    return prompt, attachments, []


def _set_input_openai_beta_threads_create(input_dict: Dict[str, Any], new_input_text: str) -> None:
    input_dict["messages"][-1]["content"] = new_input_text


# TODO
def _set_output_openai_beta_threads_create(original_output_obj: Any, output_text: str) -> None:
    # We're caching our manually-created dict.
    return {"content": output_text}


def _set_output_openai_beta_threads_create_and_poll(
    original_output_obj: Any, output_text: str
) -> None:
    """Set new output text in OpenAI beta threads create and poll response."""
    # For threads create_and_poll, we modify the message content
    try:
        if hasattr(original_output_obj, "content") and original_output_obj.content:
            if hasattr(original_output_obj.content[0], "text") and hasattr(
                original_output_obj.content[0].text, "value"
            ):
                original_output_obj.content[0].text.value = output_text
    except (IndexError, AttributeError):
        # If the structure doesn't match expected format, create a simple dict structure
        pass


def _get_output_openai_beta_threads_create_and_poll(response_obj: Any) -> str:
    """Extract the output string from a Response object or dict."""
    try:
        return response_obj.content[0].text.value
    except Exception:
        return str(response_obj)


def _get_model_openai_beta_threads_create_and_poll(input_obj: Any) -> str:
    return input_obj.model


def _get_model_openai_beta_threads_create(input_dict: Dict[str, Any]) -> str:
    return "undefined"


# ===============================================
# Anthropic.messages.create
# ===============================================


def _get_input_anthropic_messages_create(
    input_dict: Dict[str, Any],
) -> Tuple[str, List[str], List[str]]:
    messages = input_dict.get("messages", [])
    input_content = None
    attachments_list = []

    last_message = messages[-1]
    content = last_message.get("content", "")

    if isinstance(content, str):
        input_content = content
    elif isinstance(content, list):
        # Handle multi-modal content
        text_parts = []
        for item in content:
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif item.get("type") == "document":
                # Handle document attachments - create file path entry
                source = item.get("source", {})
                if source.get("type") == "base64":
                    # For now, we'll indicate this as a base64 document
                    attachments_list.append(("document.pdf", "base64_embedded"))
        input_content = " ".join(text_parts) if text_parts else str(content)

        if input_content is None:
            input_content = str(input_dict)

    return input_content, attachments_list, []


def _set_input_anthropic_messages_create(input_dict: Dict[str, Any], new_input_text: str) -> None:
    # TODO: We currently just consider the last input of messages list.
    input_dict["messages"][-1]["content"] = new_input_text


def _get_output_anthropic_messages_create(response_obj: Any) -> str:
    return response_obj.content[0].text


def _set_output_anthropic_messages_create(original_output_obj: Any, output_text: str) -> None:
    original_output_obj.content[-1].text = output_text


def _get_model_anthropic_messages_create(input_dict: Dict[str, Any]) -> str:
    return input_dict.get("model", "unknown")


# ===============================================
# together.resources.chat.completions.ChatCompletions.create
# ===============================================


def _get_input_together_resources_chat_completions_ChatCompletions_create(
    input_dict: Dict[str, Any],
) -> Tuple[str, List, List]:
    """Extract input text, attachments, and tools from Together chat completions input."""
    messages = input_dict.get("messages", [])
    if not messages:
        return str(input_dict), [], []

    # Get the last user message as the primary input
    last_message = messages[-1]
    content = last_message.get("content", "")

    # For now, no attachment or tool support in Together chat completions
    return content, [], []


def _set_input_together_resources_chat_completions_ChatCompletions_create(
    input_dict: Dict[str, Any], new_input_text: str
) -> None:
    """Set new input text in Together chat completions input."""
    input_dict["messages"][-1]["content"] = new_input_text


def _get_output_together_resources_chat_completions_ChatCompletions_create(
    response_obj: Any,
) -> str:
    """Extract output text from Together chat completions response."""
    if hasattr(response_obj, "choices") and response_obj.choices:
        choice = response_obj.choices[0]
        if hasattr(choice, "message") and hasattr(choice.message, "content"):
            return choice.message.content or ""
    return str(response_obj)


def _set_output_together_resources_chat_completions_ChatCompletions_create(
    original_output_obj: Any, output_text: str
) -> None:
    """Set new output text in Together chat completions response."""
    if hasattr(original_output_obj, "choices") and original_output_obj.choices:
        choice = original_output_obj.choices[0]
        if hasattr(choice, "message"):
            choice.message.content = output_text


def _get_model_together_resources_chat_completions_ChatCompletions_create(
    input_dict: Dict[str, Any],
) -> str:
    """Extract model name from Together chat completions input."""
    return input_dict.get("model", "unknown")


# ===============================================
# VertexAI: Client.models.generate_content
# ===============================================


def _get_input_vertex_client_models_generate_content(
    input_dict: Dict[str, Any],
) -> Tuple[str, List[str], List[str]]:
    return input_dict["contents"], [], []  # no attachments, no tools


def _set_input_vertex_client_models_generate_content(
    input_dict: Dict[str, Any], new_input_text: str
) -> None:
    # TODO: We currently just consider the case where contents is a string.
    input_dict["contents"] = new_input_text


def _get_output_vertex_client_models_generate_content(response_obj: Any) -> str:
    return response_obj.text


def _set_output_vertex_client_models_generate_content(
    original_output_obj: Any, output_text: str
) -> None:
    # Modify the original object in-place, similar to OpenAI and Anthropic patches
    # VertexAI responses typically have candidates with parts containing text
    if hasattr(original_output_obj, "candidates") and original_output_obj.candidates:
        for candidate in original_output_obj.candidates:
            if (
                hasattr(candidate, "content")
                and hasattr(candidate.content, "parts")
                and candidate.content.parts
            ):
                for part in candidate.content.parts:
                    if hasattr(part, "text"):
                        part.text = output_text
                        return
    # Fallback: if the structure doesn't match expected format, try direct text field
    elif hasattr(original_output_obj, "text"):
        original_output_obj.text = output_text


def _get_model_vertex_client_models_generate_content(input_dict: Dict[str, Any]) -> str:
    return input_dict.get("model", "unknown")


def _cache_format_vertex_client_models_generate_content(
    input_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Format VertexAI client models generate content input for caching."""
    input_text, attachments = _get_input_vertex_client_models_generate_content(input_dict)
    model_str = _get_model_vertex_client_models_generate_content(input_dict)
    return {
        "input": input_text,
        "model": model_str,
        "attachments": attachments if attachments else None,
    }


# ===============================================
# API onject helpers
# ===============================================


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
    elif api_type == "Anthropic.messages.create":
        return _get_input_anthropic_messages_create(input_dict)
    elif api_type == "vertexai client_models_generate_content":
        return _get_input_vertex_client_models_generate_content(input_dict)
    elif api_type == "OpenAI.beta.threads.create":
        return _get_input_openai_beta_threads_create(input_dict)
    elif api_type == "OpenAI.beta.threads.create_and_poll":
        return _get_input_openai_beta_threads_create_and_poll(input_dict)
    elif api_type == "together.resources.chat.completions.ChatCompletions.create":
        return _get_input_together_resources_chat_completions_ChatCompletions_create(input_dict)
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
    elif api_type == "Anthropic.messages.create":
        return _set_input_anthropic_messages_create(input_dict, new_input_text)
    elif api_type == "vertexai client_models_generate_content":
        return _set_input_vertex_client_models_generate_content(input_dict, new_input_text)
    elif api_type == "OpenAI.beta.threads.create":
        return _set_input_openai_beta_threads_create(input_dict, new_input_text)
    elif api_type == "together.resources.chat.completions.ChatCompletions.create":
        return _set_input_together_resources_chat_completions_ChatCompletions_create(
            input_dict, new_input_text
        )
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
    elif api_type == "Anthropic.messages.create":
        return _get_output_anthropic_messages_create(response_obj)
    elif api_type == "vertexai client_models_generate_content":
        return _get_output_vertex_client_models_generate_content(response_obj)
    elif api_type == "OpenAI.beta.threads.create_and_poll":
        return _get_output_openai_beta_threads_create_and_poll(response_obj)
    elif api_type == "together.resources.chat.completions.ChatCompletions.create":
        return _get_output_together_resources_chat_completions_ChatCompletions_create(response_obj)
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
    elif api_type == "Anthropic.messages.create":
        return _set_output_anthropic_messages_create(original_output_obj, new_output_text)
    elif api_type == "vertexai client_models_generate_content":
        return _set_output_vertex_client_models_generate_content(
            original_output_obj, new_output_text
        )
    elif api_type == "OpenAI.beta.threads.create_and_poll":
        return _set_output_openai_beta_threads_create_and_poll(original_output_obj, new_output_text)
    elif api_type == "together.resources.chat.completions.ChatCompletions.create":
        return _set_output_together_resources_chat_completions_ChatCompletions_create(
            original_output_obj, new_output_text
        )
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
    elif api_type == "Anthropic.messages.create":
        return _get_model_anthropic_messages_create(input_dict)
    elif api_type == "vertexai client_models_generate_content":
        return _get_model_vertex_client_models_generate_content(input_dict)
    elif api_type == "OpenAI.beta.threads.create_and_poll":
        return _get_model_openai_beta_threads_create_and_poll(input_dict)
    elif api_type == "OpenAI.beta.threads.create":
        return _get_model_openai_beta_threads_create(input_dict)
    elif api_type == "together.resources.chat.completions.ChatCompletions.create":
        return _get_model_together_resources_chat_completions_ChatCompletions_create(input_dict)
    else:
        raise ValueError(f"Unknown API type {api_type}")
