"""
Lesson injection for LLM contexts.

Queries the ao-playbook server for lessons in a given folder path
and returns them formatted as injected context.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Optional

from ao.common.constants import PLAYBOOK_SERVER_URL
from ao.common.logger import logger


def inject_lesson(path: Optional[str] = None) -> str:
    """
    Retrieve lessons from the playbook server and return them as injected context.

    Args:
        path: Folder path to retrieve lessons from (e.g. 'beaver/retriever/').
              If None, returns all lessons.

    Returns:
        The injected context string with lessons, or empty string if unavailable.
    """
    url = f"{PLAYBOOK_SERVER_URL}/api/v1/query/lessons"

    payload = {}
    if path is not None:
        payload["path"] = path

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
            return result.get("injected_context", "")
    except urllib.error.URLError as e:
        logger.warning(f"Playbook server unavailable: {e.reason}")
        return ""
    except Exception as e:
        logger.warning(f"Failed to inject lessons: {e}")
        return ""
