"""
String matching for content-based edge detection.

This module implements the matching algorithm that determines which previous
LLM outputs appear in a new LLM's input, establishing dataflow edges.
"""

from typing import List, Dict, Any
from ao.server.database_manager import DB
from ao.common.logger import logger


def find_source_nodes(
    session_id: str,
    input_dict: Dict[str, Any],
    api_type: str,
) -> List[str]:
    """
    Find source node IDs whose outputs appear in the given input.

    This is the main entry point for content-based edge detection.
    It extracts text from the input, then checks against all stored
    outputs from previous LLM calls in the session.

    Args:
        session_id: The session to search within
        input_dict: The input dictionary for the LLM call
        api_type: The API type identifier (e.g., "httpx.Client.send")

    Returns:
        List of node_ids that should have edges to the new node
    """
    from ao.runner.monkey_patching.patching_utils import extract_input_text

    input_text = extract_input_text(input_dict, api_type)
    logger.info(
        f"[DEBUG string_matching] input_text: {input_text[:200] if input_text else 'EMPTY'}..."
    )

    return find_matching_nodes(session_id, input_text)


def find_matching_nodes(session_id: str, input_text: str) -> List[str]:
    """
    Find node IDs whose stored outputs match the input text.

    Currently uses simple exact substring matching. Can be extended
    with more sophisticated heuristics (rarity weighting, minimum
    length thresholds, LCS, etc.).

    Args:
        session_id: The session to search within
        input_text: The concatenated input text to search in

    Returns:
        List of node_ids whose outputs appear in the input
    """
    return DB.find_content_matches(session_id, input_text)


def store_output_strings(
    session_id: str,
    node_id: str,
    output_obj: Any,
    api_type: str,
) -> None:
    """
    Store output strings from an LLM call for future matching.

    Args:
        session_id: The session this output belongs to
        node_id: The node ID that produced this output
        output_obj: The output object from the LLM call
        api_type: The API type identifier
    """
    from ao.runner.monkey_patching.patching_utils import extract_output_text

    output_strings = extract_output_text(output_obj, api_type)
    logger.info(f"[DEBUG string_matching] output_strings: {output_strings}")

    DB.store_llm_output(session_id, node_id, output_strings)
