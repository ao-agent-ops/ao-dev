"""
Lesson injection for LLM contexts.

This module provides functions to inject relevant lessons into context strings
by querying the ao-playbook server for semantically similar lessons.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Optional

from ao.common.constants import PLAYBOOK_SERVER_URL
from ao.common.logger import logger


def inject_lesson(context: str, top_k: Optional[int] = None) -> str:
    """
    Inject relevant lessons into a context string.

    Queries the playbook server for semantically similar lessons
    and prepends them to the context.

    Args:
        context: The context string to inject lessons into
        top_k: Number of lessons to inject (None for all lessons)

    Returns:
        The context with lessons prepended, or original context if server unavailable
    """
    url = f"{PLAYBOOK_SERVER_URL}/api/v1/query/lessons"
    payload = {"query": context}
    if top_k is not None:
        payload["top_k"] = top_k
    data = json.dumps(payload).encode("utf-8")

    headers = {"Content-Type": "application/json"}

    # Add API key if available
    api_key = os.environ.get("AO_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("injected_context", context)
    except urllib.error.URLError as e:
        logger.warning(f"Playbook server unavailable: {e.reason}")
        return context
    except Exception as e:
        logger.warning(f"Failed to inject lessons: {e}")
        return context
