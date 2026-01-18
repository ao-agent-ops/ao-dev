"""
String matching for content-based edge detection.

This module implements the matching algorithm that determines which previous
LLM outputs appear in a new LLM's input, establishing dataflow edges.

Uses word-level longest contiguous match via difflib.SequenceMatcher.
"""

import re
import json
from difflib import SequenceMatcher
from typing import List, Dict, Any, Set
from ao.common.logger import logger


# ===========================================================
# Matching Configuration
# ===========================================================

# Minimum contiguous match length (in words) to create an edge
MIN_MATCH_WORDS = 3

# Coverage threshold: output_coverage * input_coverage must exceed this
# coverage = (match_len / output_len) * (match_len / input_len)
# This catches cases where the match is significant relative to both texts
MIN_COVERAGE_PRODUCT = 0.1


# ===========================================================
# Tokenization
# ===========================================================


def split_html_content(text: str) -> List[str]:
    """
    Split text containing HTML into separate content chunks.

    Each chunk of text between HTML tags becomes a separate string.
    This allows matching on individual HTML segments independently.

    Example:
        "<div>Hello</div><p>World</p>" -> ["Hello", "World"]
    """
    if not text:
        return []

    # Check if text contains HTML tags
    if not re.search(r"<[^>]+>", text):
        return [text]  # No HTML, return as single chunk

    # Split on HTML tags and filter out empty strings
    chunks = re.split(r"<[^>]+>", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def tokenize(text: str) -> List[str]:
    """
    Tokenize text into words for matching.
    Strips HTML tags, punctuation, lowercases, and splits on whitespace.
    """
    if not text:
        return []
    # Remove HTML tags (e.g., <div>, </span>, <br/>, etc.)
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove punctuation (keep only word characters and whitespace)
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    return cleaned.split()


def compute_longest_match(output_words: List[str], input_words: List[str]) -> int:
    """
    Compute longest contiguous matching word sequence.

    Uses difflib.SequenceMatcher which is optimized for this purpose.

    Returns:
        Length of longest contiguous match in words.
    """
    if not output_words or not input_words:
        return 0
    sm = SequenceMatcher(None, output_words, input_words, autojunk=False)
    match = sm.find_longest_match(0, len(output_words), 0, len(input_words))
    return match.size


# ===========================================================
# Blacklist for content-based edge detection
# ===========================================================

# Keys to skip entirely when extracting strings for content matching.
# These are metadata/config fields that don't contain actual LLM content.
BLACKLIST_KEYS_EXACT: Set[str] = {
    # Identifiers & timestamps
    "id",
    "object",
    "created_at",
    "completed_at",
    "responseId",
    "previous_response_id",
    "prompt_cache_key",
    "safety_identifier",
    # Model & config
    "model",
    "modelVersion",
    "role",
    "type",
    "status",
    "background",
    "temperature",
    "top_p",
    "top_k",
    "top_logprobs",
    "frequency_penalty",
    "presence_penalty",
    "max_output_tokens",
    "max_tokens",
    "max_tool_calls",
    "n",
    "service_tier",
    "store",
    "truncation",
    # Tool-related
    "tool_choice",
    "tools",
    "parallel_tool_calls",
    # Stop conditions
    "stop_reason",
    "stop_sequence",
    "stop",
    "finish_reason",
    "finishReason",
    # Usage/billing (entire subtrees)
    "usage",
    "usageMetadata",
    "billing",
    # Other metadata
    "error",
    "incomplete_details",
    "instructions",
    "reasoning",
    "metadata",
    "user",
    "index",
    "logprobs",
    "annotations",
    "payer",
    "verbosity",
    "format",
    "effort",
    "summary",
    # Cache-related
    "prompt_cache_retention",
    "cache_creation",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
}

# Regex patterns for keys to skip (checked if not in exact set)
BLACKLIST_KEYS_PATTERNS = [
    re.compile(r".*_tokens$"),  # input_tokens, output_tokens, cached_tokens, etc.
    re.compile(r".*_tokens_details$"),
    re.compile(r".*_at$"),  # created_at, completed_at, etc.
    re.compile(r".*_id$"),  # session_id, response_id, etc.
    re.compile(r".*_count$"),  # promptTokenCount, totalTokenCount, etc.
    re.compile(r".*Count$"),  # camelCase versions
    re.compile(r".*_tier$"),
]


def _is_blacklisted_key(key: str) -> bool:
    """Check if a dict key should be skipped during string extraction."""
    if key in BLACKLIST_KEYS_EXACT:
        return True
    for pattern in BLACKLIST_KEYS_PATTERNS:
        if pattern.match(key):
            return True
    return False


# ===========================================================
# String extraction
# ===========================================================


def _extract_all_strings(obj: Any) -> List[str]:
    """
    Recursively extract all string values from a JSON-like object.
    Skips dict keys that match the blacklist to filter out metadata.
    """
    strings = []
    if isinstance(obj, str):
        strings.append(obj)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            if _is_blacklisted_key(key):
                continue
            strings.extend(_extract_all_strings(value))
    elif isinstance(obj, list):
        for item in obj:
            strings.extend(_extract_all_strings(item))
    return strings


def extract_input_text(input_dict: Dict[str, Any], api_type: str) -> str:
    """
    Extract textual content from an LLM input for content matching.

    Returns a single concatenated string for searching (we search if any
    stored output string appears in this input text).
    """
    try:
        if api_type in ["httpx.Client.send", "httpx.AsyncClient.send"]:
            request = input_dict.get("request")
            if request is not None:
                body = request.content
                if body:
                    body_str = body.decode("utf-8")
                    try:
                        body_json = json.loads(body_str)
                        strings = _extract_all_strings(body_json)
                        return "\n".join(strings)
                    except json.JSONDecodeError:
                        return body_str
            return ""

        elif api_type == "requests.Session.send":
            request = input_dict.get("request")
            if request is not None and hasattr(request, "body") and request.body:
                try:
                    body_json = json.loads(request.body)
                    strings = _extract_all_strings(body_json)
                    return "\n".join(strings)
                except (json.JSONDecodeError, TypeError):
                    return str(request.body) if request.body else ""
            return ""

        elif api_type == "MCP.ClientSession.send_request":
            request = input_dict.get("request")
            if request is not None:
                try:
                    if hasattr(request, "model_dump"):
                        request_dict = request.model_dump()
                    elif hasattr(request, "dict"):
                        request_dict = request.dict()
                    else:
                        request_dict = {"request": str(request)}
                    strings = _extract_all_strings(request_dict)
                    return "\n".join(strings)
                except Exception:
                    return str(request)
            return ""

        elif api_type == "genai.BaseApiClient.async_request":
            request_dict = input_dict.get("request_dict", {})
            strings = _extract_all_strings(request_dict)
            return "\n".join(strings)

        else:
            logger.warning(f"Unknown API type for text extraction: {api_type}")
            return ""

    except Exception as e:
        logger.error(f"Error extracting input text: {e}")
        return ""


def extract_output_text(output_obj: Any, api_type: str) -> List[str]:
    """
    Extract textual content from an LLM output for content matching.

    Returns a list of strings - each will be checked independently for
    substring matches in future inputs. Uses blacklist filtering to
    exclude metadata fields that would cause spurious matches.
    """
    try:
        if api_type in ["httpx.Client.send", "httpx.AsyncClient.send"]:
            if output_obj is not None and hasattr(output_obj, "content"):
                try:
                    content_json = json.loads(output_obj.content.decode("utf-8"))
                    logger.info(f"[DEBUG extract_output_text] content_json: {content_json}")
                    return _extract_all_strings(content_json)
                except (json.JSONDecodeError, AttributeError):
                    return []
            return []

        elif api_type == "requests.Session.send":
            if output_obj is not None:
                try:
                    content_json = output_obj.json()
                    return _extract_all_strings(content_json)
                except (json.JSONDecodeError, AttributeError):
                    return []
            return []

        elif api_type == "MCP.ClientSession.send_request":
            if output_obj is not None:
                try:
                    if hasattr(output_obj, "model_dump"):
                        output_dict = output_obj.model_dump()
                    elif hasattr(output_obj, "dict"):
                        output_dict = output_obj.dict()
                    else:
                        output_dict = {"output": str(output_obj)}
                    return _extract_all_strings(output_dict)
                except Exception:
                    return [str(output_obj)]
            return []

        elif api_type == "genai.BaseApiClient.async_request":
            if output_obj is not None and hasattr(output_obj, "body"):
                try:
                    body_json = json.loads(output_obj.body)
                    return _extract_all_strings(body_json)
                except (json.JSONDecodeError, AttributeError):
                    return []
            return []

        else:
            logger.warning(f"Unknown API type for text extraction: {api_type}")
            return []

    except Exception as e:
        logger.error(f"Error extracting output text: {e}")
        return []


# ===========================================================
# Session Data Management
# ===========================================================

# In-memory storage for session outputs
# Structure: {session_id: {node_id: [[word_lists]]}}
_session_outputs: Dict[str, Dict[str, List[List[str]]]] = {}


def _get_session_outputs(session_id: str) -> Dict[str, List[List[str]]]:
    """Get or create output storage for a session."""
    if session_id not in _session_outputs:
        _session_outputs[session_id] = {}
    return _session_outputs[session_id]


def clear_session_data(session_id: str) -> None:
    """Clear session data when a session is erased or restarted."""
    if session_id in _session_outputs:
        del _session_outputs[session_id]


# ===========================================================
# Content matching
# ===========================================================


def is_content_match(
    output_words: List[str],
    input_words: List[str],
) -> tuple[bool, str, int, float]:
    """
    Determine if output content matches input content.

    Returns:
        Tuple of (is_match, match_type, match_len, coverage_product)
        - is_match: True if criteria met
        - match_type: "absolute" or "coverage" or ""
        - match_len: Length of longest contiguous match
        - coverage_product: output_coverage * input_coverage
    """
    match_len = compute_longest_match(output_words, input_words)

    # Criterion 1: Absolute match length
    # if match_len >= MIN_MATCH_WORDS:
    #     coverage = (match_len / len(output_words)) * (match_len / len(input_words))
    #     return True, "absolute", match_len, coverage

    # Criterion 2: Coverage-based match
    if match_len > 0 and len(output_words) > 0 and len(input_words) > 0:
        output_coverage = match_len / len(output_words)
        input_coverage = match_len / len(input_words)
        coverage_product = output_coverage * input_coverage
        # if coverage_product >= MIN_COVERAGE_PRODUCT:
        #     return True, "coverage", match_len, coverage_product
        if output_coverage > 0.5 and match_len > MIN_MATCH_WORDS:
            return True, "coverage", match_len, coverage_product

    return False, "", match_len, 0.0


def find_source_nodes(
    session_id: str,
    input_dict: Dict[str, Any],
    api_type: str,
) -> List[str]:
    """
    Find source node IDs whose outputs appear in the given input.

    Uses longest contiguous word match. An edge is created if either:
    1. match_len >= MIN_MATCH_WORDS (absolute threshold), or
    2. output_coverage * input_coverage >= MIN_COVERAGE_PRODUCT (relative threshold)

    Args:
        session_id: The session to search within
        input_dict: The input dictionary for the LLM call
        api_type: The API type identifier (e.g., "httpx.Client.send")

    Returns:
        List of node_ids that should have edges to the new node
    """
    # Extract and tokenize input text
    input_text = extract_input_text(input_dict, api_type)
    if not input_text:
        return []

    input_words = tokenize(input_text)
    if not input_words:
        return []

    logger.debug(f"[string_matching] input has {len(input_words)} words: {input_words[:10]}...")

    # Find matches
    session_outputs = _get_session_outputs(session_id)
    matches = []

    for node_id, output_word_lists in session_outputs.items():
        for output_words in output_word_lists:
            is_match, match_type, match_len, coverage = is_content_match(output_words, input_words)
            if is_match:
                logger.info(
                    f"[string_matching] MATCH ({match_type}): node={node_id[:8]}, "
                    f"match={match_len} words, coverage={coverage:.3f}"
                )
                matches.append(node_id)
                break  # Only add node once even if multiple outputs match

    return matches


def store_output_strings(
    session_id: str,
    node_id: str,
    output_obj: Any,
    api_type: str,
) -> None:
    """
    Store output strings from an LLM call for future matching.

    Tokenizes output text for efficient matching.

    Args:
        session_id: The session this output belongs to
        node_id: The node ID that produced this output
        output_obj: The output object from the LLM call
        api_type: The API type identifier
    """
    # Extract output strings
    output_strings = extract_output_text(output_obj, api_type)
    if not output_strings:
        return

    # Split HTML content into separate chunks, then tokenize each
    session_outputs = _get_session_outputs(session_id)
    word_lists = []

    for output_str in output_strings:
        # Split HTML into separate content chunks (each becomes its own word list)
        chunks = split_html_content(output_str)
        for chunk in chunks:
            words = tokenize(chunk)
            if words:
                word_lists.append(words)
                logger.debug(
                    f"[string_matching] stored output: {len(words)} words, " f"node={node_id[:8]}"
                )

    if word_lists:
        session_outputs[node_id] = word_lists
