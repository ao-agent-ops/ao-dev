import os
import zipfile
import tempfile
import asyncio
import threading
import base64
import getpass
from pathlib import Path
from aco.common.constants import COLLECT_TELEMETRY, TELEMETRY_USERNAME
from aco.common.logger import logger
from aco.server.telemetry.client import supabase_client
from typing import Optional


# File extensions to include in code snapshots
INCLUDE_EXTENSIONS = {".py", ".ipynb"}


def get_user_id() -> str:
    """Get a user identifier for telemetry purposes."""
    return TELEMETRY_USERNAME


def _should_include(path: Path) -> bool:
    """Check if a file should be included in the snapshot."""
    return path.suffix in INCLUDE_EXTENSIONS


def create_code_zip(project_root: str) -> bytes:
    """Create a zip file of the project code, excluding common artifacts."""
    project_path = Path(project_root)

    with tempfile.NamedTemporaryFile() as temp_file:
        with zipfile.ZipFile(temp_file.name, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in project_path.rglob("*"):
                if file_path.is_file() and _should_include(file_path):
                    # Add file to zip with relative path
                    arcname = file_path.relative_to(project_path)
                    try:
                        zipf.write(file_path, arcname)
                    except (OSError, PermissionError) as e:
                        logger.debug(f"Skipping file {file_path}: {e}")

        # Read the zip data
        temp_file.seek(0)
        return temp_file.read()


def store_code_snapshot(
    user_id: str, project_root: str, user_actions: Optional[str] = None
) -> bool:
    """Store a code snapshot synchronously with optional UI event reference."""
    if not COLLECT_TELEMETRY:
        return False

    if not supabase_client.is_available():
        logger.debug("Supabase not available, skipping code snapshot")
        return False

    try:
        # Create zip
        zip_data = create_code_zip(project_root)

        # Encode binary data as base64 for JSON transport
        zip_data_b64 = base64.b64encode(zip_data).decode("utf-8")

        # Debug the encoding
        logger.debug(f"Original zip size: {len(zip_data)} bytes")
        logger.debug(f"Base64 encoded size: {len(zip_data_b64)} chars")
        logger.debug(f"Base64 preview: {zip_data_b64[:50]}...")
        logger.debug(f"Base64 is valid text: {zip_data_b64.isprintable()}")

        # Prepare data for storage
        data = {"user_id": user_id, "code_snapshot": zip_data_b64, "snapshot_size": len(zip_data)}

        # Add ui_event foreign key if provided
        if user_actions:
            data["user_action_id"] = user_actions

        # Store in Supabase
        supabase_client.client.table("code_snapshots").insert(data).execute()

        logger.info(f"Code snapshot stored successfully ({len(zip_data)} bytes)")
        return True

    except Exception as e:
        logger.error(f"Failed to store code snapshot: {e}")
        return False


async def store_code_snapshot_async(
    user_id: str, project_root: str, user_actions: Optional[str] = None
) -> bool:
    """Store a code snapshot asynchronously in a thread pool."""
    if not COLLECT_TELEMETRY:
        return False

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, store_code_snapshot, user_id, project_root, user_actions
    )


def store_code_snapshot_background(
    user_id: str, project_root: str, user_actions: Optional[str] = None
) -> None:
    """Store a code snapshot in the background using threading."""
    if not COLLECT_TELEMETRY:
        return

    def _background_task():
        store_code_snapshot(user_id, project_root, user_actions)

    thread = threading.Thread(target=_background_task, daemon=True)
    thread.start()


def capture_current_project_snapshot(
    project_root: str = None, user_actions: Optional[str] = None
) -> bool:
    """
    Convenience function to capture a snapshot of the current project.

    Args:
        project_root: Optional project root path. If None, uses current working directory.
        user_actions: Optional UI event ID for foreign key reference.

    Returns:
        bool: True if snapshot was successful, False otherwise.
    """
    if project_root is None:
        project_root = os.getcwd()

    user_id = get_user_id()
    return store_code_snapshot(user_id, project_root, user_actions)
