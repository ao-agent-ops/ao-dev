import hashlib
import os
import dill

from workflow_edits.cache_manager import CACHE

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


def _get_input_openai_chat_completions_create(input_obj: any) -> tuple[str, list]:
    """Extract input text and attachments from OpenAI chat completions input."""
    messages = input_obj.get("messages", [])
    if not messages:
        return "", []

    # Get the last user message as the primary input
    last_message = messages[-1]
    content = last_message.get("content", "")

    # For now, no attachment support in chat completions
    return content, []


def _set_input_openai_chat_completions_create(
    prev_input_pickle: bytes, new_input_text: str
) -> bytes:
    """Set new input text in OpenAI chat completions input."""
    input_obj = dill.loads(prev_input_pickle)
    if "messages" in input_obj and input_obj["messages"]:
        # Update the last message content
        input_obj["messages"][-1]["content"] = new_input_text
    return dill.dumps(input_obj)


def _get_output_openai_chat_completions_create(response_obj: any) -> str:
    """Extract output text from OpenAI chat completions response."""
    if hasattr(response_obj, "choices") and response_obj.choices:
        choice = response_obj.choices[0]
        if hasattr(choice, "message") and hasattr(choice.message, "content"):
            return choice.message.content or ""
    return ""


def _set_output_openai_chat_completions_create(
    prev_output_pickle: bytes, output_text: str
) -> bytes:
    """Set new output text in OpenAI chat completions response."""
    response_obj = dill.loads(prev_output_pickle)
    if hasattr(response_obj, "choices") and response_obj.choices:
        choice = response_obj.choices[0]
        if hasattr(choice, "message"):
            choice.message.content = output_text
    return dill.dumps(response_obj)


def _get_model_openai_chat_completions_create(input_obj: any) -> str:
    """Extract model name from OpenAI chat completions input."""
    return input_obj.get("model", "unknown")


# ===============================================
# OpenAI.responses.create
# ===============================================


def _get_input_openai_responses_create(input_obj: any) -> str:
    return input_obj["input"], None  # no attachments


def _set_input_openai_responses_create(prev_input_pickle: bytes, new_input_text: str) -> bytes:
    input_obj = dill.loads(prev_input_pickle)
    input_obj["input"] = new_input_text
    return dill.dumps(input_obj)


def _get_output_openai_responses_create(response_obj: bytes):
    return response_obj.output[-1].content[-1].text


def _set_output_openai_responses_create(prev_output_pickle: bytes, output_text: str) -> bytes:
    response_obj = dill.loads(prev_output_pickle)
    response_obj.output[-1].content[-1].text = output_text
    return dill.dumps(response_obj)


def _get_model_openai_responses_create(input_obj: any) -> str:
    return input_obj.get("model", "unknown")


# ===============================================
# OpenAI.beta.threads.create (OpenAI assistants)
# ===============================================


def get_cachable_input_openai_beta_threads_create(input_obj: any) -> dict:
    if isinstance(input_obj, dict):
        # For thread create, the input is a dict.
        message = input_obj["messages"][0]["content"]
        attachments = input_obj["messages"][0]["attachments"]
    else:
        # For create_and_poll, the input is an object.
        message = input_obj.content[0].text.value
        attachments = input_obj.attachments
    return {"messages": message, "attachments": attachments}


def _get_input_openai_beta_threads_create(input_obj: any) -> tuple[str, list[str]]:
    # Get paths to cached attachments.
    message = input_obj.content[0].text.value
    attachments = [attachment.file_id for attachment in input_obj.attachments]
    attachments = CACHE.attachment_ids_to_paths(attachments)
    # Convert into format [(name, path), ...]
    attachments = [[os.path.basename(path), path] for path in attachments]
    return message, attachments


def _set_input_openai_beta_threads_create(prev_input_pickle: bytes, new_input_text: str) -> bytes:
    # We're caching our manually-created dict.
    # TODO: Changing attachments. Also needs UI support.
    input_dict = dill.loads(prev_input_pickle)
    input_dict["messages"] = new_input_text
    return dill.dumps(input_dict)


def _set_output_openai_beta_threads_create(prev_output_pickle: bytes, output_text: str) -> bytes:
    # We're caching our manually-created dict.
    cachable_output = {"content": output_text}
    return dill.dumps(output_text)


def _get_output_openai_beta_threads_create(response_obj: any):
    """Extract the output string from a Response object or dict."""
    try:
        return response_obj.content[0].text.value
    except Exception:
        return str(response_obj)


def _get_model_openai_beta_threads_create(input_obj: any) -> str:
    return input_obj.model


# ===============================================
# Anthropic.messages.create
# ===============================================


def _get_input_anthropic_messages_create(input_obj: any) -> str:
    messages = input_obj.get("messages", [])
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
            input_content = str(input_obj)

    return input_content, attachments_list


def _set_input_anthropic_messages_create(prev_input_pickle: bytes, new_input_text: str) -> bytes:
    # TODO: We currently just consider the last input of messages list.
    input_obj = dill.loads(prev_input_pickle)
    input_obj["messages"][-1]["content"] = new_input_text
    return dill.dumps(input_obj)


def _get_output_anthropic_messages_create(response_obj: any):
    return response_obj.content[0].text


def _set_output_anthropic_messages_create(prev_output_pickle: bytes, output_text: str) -> bytes:
    response_obj = dill.loads(prev_output_pickle)
    response_obj.content[-1].text = output_text
    return dill.dumps(response_obj)


def _get_model_anthropic_messages_create(input_obj: any) -> str:
    return input_obj.get("model", "unknown")


# ===============================================
# VertexAI: Client.models.generate_content
# ===============================================


def _get_input_vertex_client_models_generate_content(input_obj: any) -> str:
    return input_obj["contents"], None  # no attachments


def _set_input_vertex_client_models_generate_content(
    prev_input_pickle: bytes, new_input_text: str
) -> bytes:
    # TODO: We currently just consider the case where contents is a string.
    input_obj = dill.loads(prev_input_pickle)
    input_obj["contents"] = new_input_text
    return dill.dumps(input_obj)


def _get_output_vertex_client_models_generate_content(response_obj: any) -> str:
    return response_obj.text


def _set_output_vertex_client_models_generate_content(
    prev_output_pickle: bytes, output_text: str
) -> bytes:
    from google.genai.types import GenerateContentResponse

    response_obj = dill.loads(prev_output_pickle)
    response_dict = response_obj.model_dump()
    # VertexAI responses typically have candidates with parts containing text
    if "candidates" in response_dict and isinstance(response_dict["candidates"], list):
        for candidate in response_dict["candidates"]:
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "text" in part:
                        part["text"] = output_text
                        break
                break
    # Fallback: if the structure doesn't match expected format, try direct text field
    elif "text" in response_dict:
        response_dict["text"] = output_text
    response_obj = GenerateContentResponse.model_validate(response_dict)
    return dill.dumps(response_obj)


def _get_model_vertex_client_models_generate_content(input_obj: any) -> str:
    return input_obj.get("model", "unknown")


# ===============================================
# API onject helpers
# ===============================================


def get_input(input_obj: any, api_type: str) -> str:
    if api_type == "OpenAI.chat.completions.create":
        return _get_input_openai_chat_completions_create(input_obj)
    elif api_type == "AsyncOpenAI.chat.completions.create":
        return _get_input_openai_chat_completions_create(input_obj)
    elif api_type == "OpenAI.responses.create":
        return _get_input_openai_responses_create(input_obj)
    elif api_type == "AsyncOpenAI.responses.create":
        return _get_input_openai_responses_create(input_obj)
    elif api_type == "Anthropic.messages.create":
        return _get_input_anthropic_messages_create(input_obj)
    elif api_type == "vertexai client_models_generate_content":
        return _get_input_vertex_client_models_generate_content(input_obj)
    elif api_type == "OpenAI.beta.threads.create":
        return _get_input_openai_beta_threads_create(input_obj)
    else:
        raise ValueError(f"Unknown API type {api_type}")


def set_input_string(prev_input_pickle: bytes, new_input_text: str, api_type):
    """Returns pickle with changed input text."""
    if api_type == "OpenAI.chat.completions.create":
        return _set_input_openai_chat_completions_create(prev_input_pickle, new_input_text)
    elif api_type == "AsyncOpenAI.chat.completions.create":
        return _set_input_openai_chat_completions_create(prev_input_pickle, new_input_text)
    elif api_type == "OpenAI.responses.create":
        return _set_input_openai_responses_create(prev_input_pickle, new_input_text)
    elif api_type == "AsyncOpenAI.responses.create":
        return _set_input_openai_responses_create(prev_input_pickle, new_input_text)
    elif api_type == "Anthropic.messages.create":
        return _set_input_anthropic_messages_create(prev_input_pickle, new_input_text)
    elif api_type == "vertexai client_models_generate_content":
        return _set_input_vertex_client_models_generate_content(prev_input_pickle, new_input_text)
    elif api_type == "OpenAI.beta.threads.create":
        return _set_input_openai_beta_threads_create(prev_input_pickle, new_input_text)
    else:
        raise ValueError(f"Unknown API type {api_type}")


def get_output_string(response_pickle: bytes, api_type: str) -> str:
    if api_type == "OpenAI.chat.completions.create":
        return _get_output_openai_chat_completions_create(response_pickle)
    elif api_type == "AsyncOpenAI.chat.completions.create":
        return _get_output_openai_chat_completions_create(response_pickle)
    elif api_type == "OpenAI.responses.create":
        return _get_output_openai_responses_create(response_pickle)
    elif api_type == "AsyncOpenAI.responses.create":
        return _get_output_openai_responses_create(response_pickle)
    elif api_type == "Anthropic.messages.create":
        return _get_output_anthropic_messages_create(response_pickle)
    elif api_type == "vertexai client_models_generate_content":
        return _get_output_vertex_client_models_generate_content(response_pickle)
    elif api_type == "OpenAI.beta.threads.create":
        return _get_output_openai_beta_threads_create(response_pickle)
    else:
        raise ValueError(f"Unknown API type {api_type}")


def set_output_string(prev_output_pickle: bytes, new_output_text: str, api_type):
    if api_type == "OpenAI.chat.completions.create":
        return _set_output_openai_chat_completions_create(prev_output_pickle, new_output_text)
    elif api_type == "AsyncOpenAI.chat.completions.create":
        return _set_output_openai_chat_completions_create(prev_output_pickle, new_output_text)
    elif api_type == "OpenAI.responses.create":
        return _set_output_openai_responses_create(prev_output_pickle, new_output_text)
    elif api_type == "AsyncOpenAI.responses.create":
        return _set_output_openai_responses_create(prev_output_pickle, new_output_text)
    elif api_type == "Anthropic.messages.create":
        return _set_output_anthropic_messages_create(prev_output_pickle, new_output_text)
    elif api_type == "vertexai client_models_generate_content":
        return _set_output_vertex_client_models_generate_content(
            prev_output_pickle, new_output_text
        )
    elif api_type == "OpenAI.beta.threads.create":
        return _get_output_openai_beta_threads_create(prev_output_pickle, new_output_text)
    else:
        raise ValueError(f"Unknown API type {api_type}")


def get_model_name(input_obj: bytes, api_type: str) -> str:
    if api_type == "OpenAI.chat.completions.create":
        return _get_model_openai_chat_completions_create(input_obj)
    elif api_type == "AsyncOpenAI.chat.completions.create":
        return _get_model_openai_chat_completions_create(input_obj)
    elif api_type == "OpenAI.responses.create":
        return _get_model_openai_responses_create(input_obj)
    elif api_type == "AsyncOpenAI.responses.create":
        return _get_model_openai_responses_create(input_obj)
    elif api_type == "Anthropic.messages.create":
        return _get_model_anthropic_messages_create(input_obj)
    elif api_type == "vertexai client_models_generate_content":
        return _get_model_vertex_client_models_generate_content(input_obj)
    elif api_type == "OpenAI.beta.threads.create":
        return _get_model_openai_beta_threads_create(input_obj)
    else:
        raise ValueError(f"Unknown API type {api_type}")
