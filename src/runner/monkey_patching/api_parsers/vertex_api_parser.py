from typing import Any, Dict, List, Tuple


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
