"""
Lesson injection for LLM contexts.

Queries the ao-playbook server for lessons in a given folder path
and returns them formatted as injected context. Automatically tracks
which lessons were applied to which sessions.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Optional, List, Tuple

from ao.common.constants import PLAYBOOK_SERVER_URL
from ao.common.logger import logger


def _fetch_lessons(path: Optional[str] = None) -> Tuple[str, List[str]]:
    """
    Fetch lessons from ao-playbook server.

    Args:
        path: Folder path to retrieve lessons from.

    Returns:
        Tuple of (injected_context, list of lesson_ids)
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
            injected_context = result.get("injected_context", "")
            lessons = result.get("lessons", [])
            lesson_ids = [lesson.get("id") for lesson in lessons if lesson.get("id")]
            return injected_context, lesson_ids
    except urllib.error.URLError as e:
        logger.warning(f"Playbook server unavailable: {e.reason}")
        return "", []
    except Exception as e:
        logger.warning(f"Failed to fetch lessons: {e}")
        return "", []


def inject_lesson(path: Optional[str] = None) -> str:
    """
    Retrieve lessons from the playbook server and return them as injected context.

    When called within an ao-record session, automatically tracks which lessons
    were applied so the UI can display "Applied to: Run X" for each lesson.

    Args:
        path: Folder path to retrieve lessons from (e.g. 'beaver/retriever/').
              If None, returns all lessons.

    Returns:
        The injected context string with lessons, or empty string if unavailable.
    """
    # Fetch lessons from ao-playbook
    injected_context, lesson_ids = _fetch_lessons(path)

    # Track which lessons were applied to this session
    if lesson_ids:
        try:
            from ao.runner.context_manager import get_session_id
            session_id = get_session_id()

            if session_id:
                from ao.server.database_manager import DB
                for lesson_id in lesson_ids:
                    DB.add_lesson_applied(lesson_id, session_id)
                logger.debug(f"Tracked {len(lesson_ids)} lessons applied to session {session_id[:8]}")
        except Exception as e:
            # Don't fail lesson injection if tracking fails
            logger.debug(f"Could not track lesson application: {e}")

    return injected_context
