from typing import Any, Dict, List, Tuple


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
