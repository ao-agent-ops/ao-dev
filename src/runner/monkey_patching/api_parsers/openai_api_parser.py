import os
import json
from typing import Any, Dict, List, Tuple
from aco.common.logger import logger


# --------------------- Helper functions ---------------------


def _deep_serialize(obj: Any) -> Any:
    """Recursively serialize objects to JSON-compatible format."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, dict):
        return {k: _deep_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_deep_serialize(item) for item in obj]
    elif hasattr(obj, "__dict__"):
        # Convert object to dict and recursively serialize
        result = {}
        for k, v in vars(obj).items():
            result[k] = _deep_serialize(v)
        return result
    else:
        return str(obj)


def _serialize_chat_completion_message(message: Any) -> Dict[str, Any]:
    """Serialize a ChatCompletionMessage to JSON-compatible format."""
    serialized = {}

    # Basic fields
    if hasattr(message, "role"):
        serialized["role"] = message.role
    elif isinstance(message, dict) and "role" in message:
        serialized["role"] = message["role"]
    else:
        serialized["role"] = "assistant"

    if hasattr(message, "content"):
        serialized["content"] = message.content
    elif isinstance(message, dict) and "content" in message:
        serialized["content"] = message["content"]

    # Optional fields - use deep serialization for nested objects
    for field in ["refusal", "function_call", "tool_calls", "audio", "annotations"]:
        if hasattr(message, field):
            value = getattr(message, field)
            if value is not None:
                serialized[field] = _deep_serialize(value)
        elif isinstance(message, dict) and field in message:
            value = message[field]
            if value is not None:
                serialized[field] = _deep_serialize(value)

    return serialized


def _serialize_choice(choice: Any) -> Dict[str, Any]:
    """Serialize a ChatCompletion Choice to JSON-compatible format."""
    from openai.types.chat.chat_completion import Choice

    choice: Choice
    serialized = {}

    # Required fields - Choice always has these
    serialized["index"] = choice.index
    serialized["finish_reason"] = choice.finish_reason
    serialized["message"] = _serialize_chat_completion_message(choice.message)

    # Optional logprobs - only include if not None
    if choice.logprobs is not None:
        serialized["logprobs"] = _deep_serialize(choice.logprobs)

    return serialized


def _serialize_usage(usage: Any) -> Dict[str, Any]:
    """Serialize CompletionUsage to JSON-compatible format."""
    from openai.types.completion_usage import CompletionUsage

    if usage is None:
        return None

    usage: CompletionUsage
    serialized = {}

    # Required fields - CompletionUsage always has these
    serialized["prompt_tokens"] = usage.prompt_tokens
    serialized["completion_tokens"] = usage.completion_tokens
    serialized["total_tokens"] = usage.total_tokens

    # Optional details - only include if not None
    if usage.prompt_tokens_details is not None:
        serialized["prompt_tokens_details"] = vars(usage.prompt_tokens_details)

    if usage.completion_tokens_details is not None:
        serialized["completion_tokens_details"] = vars(usage.completion_tokens_details)

    return serialized


# --------------------- API patches ---------------------


def _get_input_openai_chat_completions_create(
    input_dict: Dict[str, Any],
) -> Tuple[str, List[str], List[str]]:
    """Serialize OpenAI chat completions input to JSON string.

    Returns:
        Tuple of (json_str, attachments, tools):
        - json_str: JSON representation of the input
        - attachments: List of attachment file IDs referenced in messages
        - tools: List of tool/function names used in the request
    """
    from openai._types import NOT_GIVEN

    serialized = {}
    attachments = []
    tools = []

    # Serialize all fields, handling NOT_GIVEN sentinel
    for key, value in input_dict.items():
        if value is NOT_GIVEN:
            serialized[key] = "NOT_GIVEN"
        elif key == "messages":
            # Serialize messages array
            serialized[key] = []
            for msg in value:
                serialized_msg = _serialize_chat_completion_message(msg)
                serialized[key].append(serialized_msg)
        elif key == "tools":
            # Serialize tools and extract tool names
            serialized[key] = _deep_serialize(value)
            for tool in value:
                if isinstance(tool, dict) and "function" in tool:
                    if isinstance(tool["function"], dict) and "name" in tool["function"]:
                        tools.append(tool["function"]["name"])
                elif hasattr(tool, "function") and hasattr(tool.function, "name"):
                    tools.append(tool.function.name)
        else:
            # Deep serialize everything else
            serialized[key] = _deep_serialize(value)

    json_str = json.dumps(serialized, indent=2, ensure_ascii=False)
    return json_str, attachments, tools


def _set_input_openai_chat_completions_create(
    original_input_dict: Dict[str, Any], new_input_text: str
) -> None:
    """Deserialize JSON string back to OpenAI chat completions input dict.

    This updates the original_input_dict in-place with values from the JSON string.
    Handles reconstruction of NOT_GIVEN sentinels and proper message structures.
    """
    from openai._types import NOT_GIVEN

    # Parse JSON
    new_data = json.loads(new_input_text)

    # Clear the original dict and repopulate it
    original_input_dict.clear()

    # Restore all fields, handling NOT_GIVEN sentinel
    for key, value in new_data.items():
        if value == "NOT_GIVEN":
            original_input_dict[key] = NOT_GIVEN
        else:
            original_input_dict[key] = value


def _get_output_openai_chat_completions_create(response_obj: Any) -> str:
    """Serialize complete ChatCompletion response to JSON string.

    Returns a JSON string representation of the entire ChatCompletion object
    that can be deserialized back to its original form.
    """
    from openai.types.chat import ChatCompletion

    response_obj: ChatCompletion
    serialized = {}

    # Required fields - ChatCompletion always has these
    serialized["id"] = response_obj.id
    serialized["object"] = response_obj.object
    serialized["created"] = response_obj.created
    serialized["model"] = response_obj.model
    serialized["choices"] = [_serialize_choice(choice) for choice in response_obj.choices]

    # Optional fields - only include if not None
    if response_obj.usage is not None:
        serialized["usage"] = _serialize_usage(response_obj.usage)

    if response_obj.system_fingerprint is not None:
        serialized["system_fingerprint"] = response_obj.system_fingerprint

    if response_obj.service_tier is not None:
        serialized["service_tier"] = response_obj.service_tier

    # Convert to JSON string
    return json.dumps(serialized, indent=2, ensure_ascii=False)


def _set_output_openai_chat_completions_create(original_output_obj: Any, output_text: str) -> None:
    """Deserialize JSON string back to ChatCompletion response object.

    This updates the original_output_obj in-place with values from the JSON string.
    """
    from openai.types.chat.chat_completion import ChatCompletion, Choice, CompletionUsage
    from openai.types.chat.chat_completion_message import (
        ChatCompletionMessage,
        FunctionCall,
        AnnotationURLCitation,
        Annotation,
        ChatCompletionAudio,
    )
    from openai.types.completion_usage import CompletionTokensDetails, PromptTokensDetails
    from openai.types.chat.chat_completion_message_tool_call import (
        ChatCompletionMessageToolCall,
        Function,
    )

    # Parse JSON
    logger.debug(f"[OutputOpenAI] original_output_obj: {original_output_obj}")
    logger.debug(f"[OutputOpenAI] output_text: {output_text}")
    new_data = json.loads(output_text)
    logger.debug(f"[OutputOpenAI] new_data: {new_data}")

    # Update required fields
    original_output_obj: ChatCompletion
    original_output_obj.id = new_data["id"]
    original_output_obj.created = new_data["created"]
    original_output_obj.model = new_data["model"]
    original_output_obj.object = new_data["object"]
    original_output_obj.service_tier = new_data.get("service_tier", None)
    original_output_obj.system_fingerprint = new_data.get("system_fingerprint", None)

    # Update choices - create new choices from JSON dict
    choices = []
    for choice_data in new_data["choices"]:
        message_data = choice_data["message"]

        content = message_data.get("content", None)
        refusal = message_data.get("refusal", None)
        role = message_data["role"]

        annotations = None
        if "annotations" in message_data:
            annotations = []
            for annotation_data in message_data["annotations"]:
                annotation_type = annotation_data["type"]
                url_citation_data = annotation_data["url_citation"]
                url_citation = AnnotationURLCitation(
                    end_index=url_citation_data["end_index"],
                    start_index=url_citation_data["start_index"],
                    title=url_citation_data["title"],
                    url=url_citation_data["url"],
                )
                annotations.append(Annotation(type=annotation_type, url_citation=url_citation))

        audio = None
        if "audio" in message_data and message_data["audio"]:
            audio = ChatCompletionAudio(**message_data["audio"])

        # Handle function_call
        function_call = None
        if "function_call" in message_data and message_data["function_call"]:
            function_call = FunctionCall(**message_data["function_call"])

        # Handle tool_calls
        tool_calls = None
        if "tool_calls" in message_data and message_data["tool_calls"]:
            tool_calls = []
            for tc_data in message_data["tool_calls"]:
                func = Function(**tc_data["function"])
                tool_call = ChatCompletionMessageToolCall(
                    id=tc_data["id"],
                    type=tc_data["type"],
                    function=func,
                )
                tool_calls.append(tool_call)

        # Create message
        message = ChatCompletionMessage(
            content=content,
            refusal=refusal,
            role=role,
            annotations=annotations,
            audio=audio,
            function_call=function_call,
            tool_calls=tool_calls,
        )

        # Handle logprobs
        logprobs = None
        if "logprobs" in choice_data and choice_data["logprobs"]:
            from openai.types.chat.chat_completion import ChoiceLogprobs
            from openai.types.chat.chat_completion_token_logprob import (
                ChatCompletionTokenLogprob,
                TopLogprob,
            )

            logprobs_data = choice_data["logprobs"]

            # Reconstruct content token logprobs
            content_logprobs = None
            if "content" in logprobs_data and logprobs_data["content"]:
                content_logprobs = []
                for token_data in logprobs_data["content"]:
                    # Reconstruct top_logprobs
                    top_logprobs = []
                    for top_data in token_data.get("top_logprobs", []):
                        top_logprobs.append(
                            TopLogprob(
                                token=top_data["token"],
                                logprob=top_data["logprob"],
                                bytes=top_data.get("bytes"),
                            )
                        )

                    # Create ChatCompletionTokenLogprob
                    content_logprobs.append(
                        ChatCompletionTokenLogprob(
                            token=token_data["token"],
                            logprob=token_data["logprob"],
                            bytes=token_data.get("bytes"),
                            top_logprobs=top_logprobs,
                        )
                    )

            # Reconstruct refusal token logprobs (if any)
            refusal_logprobs = None
            if "refusal" in logprobs_data and logprobs_data["refusal"]:
                refusal_logprobs = []
                for token_data in logprobs_data["refusal"]:
                    # Reconstruct top_logprobs
                    top_logprobs = []
                    for top_data in token_data.get("top_logprobs", []):
                        top_logprobs.append(
                            TopLogprob(
                                token=top_data["token"],
                                logprob=top_data["logprob"],
                                bytes=top_data.get("bytes"),
                            )
                        )

                    # Create ChatCompletionTokenLogprob
                    refusal_logprobs.append(
                        ChatCompletionTokenLogprob(
                            token=token_data["token"],
                            logprob=token_data["logprob"],
                            bytes=token_data.get("bytes"),
                            top_logprobs=top_logprobs,
                        )
                    )

            # Create ChoiceLogprobs
            logprobs = ChoiceLogprobs(
                content=content_logprobs,
                refusal=refusal_logprobs,
            )

        # Create choice
        choice = Choice(
            finish_reason=choice_data.get("finish_reason"),
            index=choice_data.get("index"),
            message=message,
            logprobs=logprobs,
        )
        choices.append(choice)

    # Assign the newly created choices list to the original object
    original_output_obj.choices = choices

    usage = None
    if "usage" in new_data and new_data["usage"]:
        usage_data = new_data["usage"]
        completion_tokens = usage_data["completion_tokens"]
        prompt_tokens = usage_data["prompt_tokens"]
        total_tokens = usage_data["total_tokens"]
        completion_tokens_details = None
        if "completion_tokens_details" in usage_data and usage_data["completion_tokens_details"]:
            completion_tokens_details = CompletionTokensDetails(
                **usage_data["completion_tokens_details"]
            )
        prompt_tokens_details = None
        if "prompt_tokens_details" in usage_data and usage_data["prompt_tokens_details"]:
            prompt_tokens_details = PromptTokensDetails(**usage_data["prompt_tokens_details"])
        usage = CompletionUsage(
            completion_tokens=completion_tokens,
            prompt_tokens=prompt_tokens,
            total_tokens=total_tokens,
            completion_tokens_details=completion_tokens_details,
            prompt_tokens_details=prompt_tokens_details,
        )
    original_output_obj.choices = choices
    original_output_obj.usage = usage


def _get_model_openai_chat_completions_create(input_dict: Dict[str, Any]) -> str:
    """Extract model name from OpenAI chat completions input."""
    return input_dict.get("model", "unknown")


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
# API object helpers
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
    elif api_type == "OpenAI.beta.threads.create":
        return _get_input_openai_beta_threads_create(input_dict)
    elif api_type == "OpenAI.beta.threads.create_and_poll":
        return _get_input_openai_beta_threads_create_and_poll(input_dict)
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
    elif api_type == "OpenAI.beta.threads.create":
        return _set_output_openai_beta_threads_create(original_output_obj, new_output_text)
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
    else:
        raise ValueError(f"Unknown API type {api_type}")
