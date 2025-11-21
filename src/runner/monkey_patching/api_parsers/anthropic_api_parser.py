from typing import Any, Dict, List, Tuple


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
