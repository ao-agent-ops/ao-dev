import json
import os
from typing import Dict, Any, Optional
from aco.common.logger import logger
from aco.server.telemetry.client import supabase_client
from aco.server.telemetry.snapshots import get_user_id, store_code_snapshot_background
from aco.common.constants import COLLECT_TELEMETRY


def log_server_message(msg: Dict[str, Any], session_graphs: Dict[str, Any]) -> None:
    """
    Log a server message to telemetry.

    Args:
        msg: The message dictionary containing type, session_id, and other data
        session_graphs: Dictionary of session_id -> graph_data for accessing current state
    """
    if not COLLECT_TELEMETRY:
        return

    if not supabase_client.is_available():
        logger.debug("Supabase not available, skipping server message logging")
        return

    try:
        event_type = msg.get("type", "unknown")
        session_id = msg.get("session_id")
        user_id = get_user_id()

        # Skip certain message types
        if event_type in ["get_graph", "clear", "add_node", "shutdown"]:
            logger.debug(f"Skipping telemetry for message type: {event_type}")
            return

        # Prepare event data based on message type
        event_data = _prepare_event_data(msg, session_graphs, event_type)

        # Adjust event type for input/output edits to distinguish them
        final_event_type = event_type
        if event_type == "edit_input":
            final_event_type = "input_edit"
        elif event_type == "edit_output":
            final_event_type = "output_edit"

        response = (
            supabase_client.client.table("user_actions")
            .insert(
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "event_type": final_event_type,
                    "event_data": json.dumps(event_data),
                }
            )
            .execute()
        )

        logger.debug(f"Server message logged to telemetry: {final_event_type}")

        # Get the user_action ID for potential code snapshot
        user_action_id = None
        if response.data and len(response.data) > 0:
            user_action_id = response.data[0].get("id")
            logger.debug(f"User action ID: {user_action_id} for event type: {final_event_type}")
        else:
            logger.warning(f"No user_action ID returned for event type: {final_event_type}")
            logger.warning(f"Response data: {response.data}")

        # Create code snapshot for rerun or first-time run messages
        if event_type == "restart" or _is_first_time_run(msg):
            _capture_code_snapshot_for_run(msg, user_id, user_action_id)

        # Create user log entry for "log" messages
        if event_type == "log":
            logger.debug(
                f"Processing log message: session_id={session_id}, entry='{msg.get('entry', '')[:50]}...'"
            )
            _create_user_log_entry(msg, user_id, user_action_id)

    except Exception as e:
        logger.error(f"Failed to log server message to telemetry: {e}")


def _prepare_event_data(
    msg: Dict[str, Any], session_graphs: Dict[str, Any], event_type: str
) -> Dict[str, Any]:
    """
    Prepare event data based on message type with specific handling for different types.

    Args:
        msg: The server message
        session_graphs: Dictionary of session_id -> graph_data
        event_type: The type of the message

    Returns:
        Dict containing the prepared event data
    """
    event_data = msg.copy()
    session_id = msg.get("session_id")

    if event_type == "deregister":
        # Include the full graph with inputs/outputs in event_data
        if session_id and session_id in session_graphs:
            event_data["graph_state"] = session_graphs[session_id]
        else:
            event_data["graph_state"] = None

    elif event_type in ["edit_input", "edit_output"]:
        # Add previous value for input/output edits
        node_id = msg.get("node_id")
        field = "input" if event_type == "edit_input" else "output"

        # Find the current value in session_graphs
        previous_value = ""
        if session_id and session_id in session_graphs:
            for node in session_graphs[session_id].get("nodes", []):
                if node.get("id") == node_id:
                    previous_value = node.get(field, "")
                    break

        event_data["previous_value"] = previous_value
        event_data["field"] = field

    return event_data


def _is_first_time_run(msg: Dict[str, Any]) -> bool:
    """
    Check if this message represents a first-time run.
    This could be based on message type or content indicating a new experiment.
    """
    event_type = msg.get("type", "")

    # Check for messages that indicate a new run
    if event_type == "add_subrun":
        # If prev_session_id is None, it's a first-time run
        return msg.get("prev_session_id") is None

    return False


def _capture_code_snapshot_for_run(
    msg: Dict[str, Any], user_id: str, user_action_id: Optional[str]
) -> None:
    """
    Capture a code snapshot for run-related messages in the background.

    Args:
        msg: The server message
        user_id: User identifier
        user_action_id: ID of the user_action entry to reference
    """
    try:
        # Try to get project root from message or use current working directory
        project_root = msg.get("cwd") or os.getcwd()

        # Capture snapshot in background to avoid blocking
        store_code_snapshot_background(user_id, project_root, user_action_id)

        logger.debug(f"Code snapshot capture initiated for {msg.get('type')} event")

    except Exception as e:
        logger.error(f"Failed to initiate code snapshot capture: {e}")


def _create_user_log_entry(
    msg: Dict[str, Any], user_id: str, user_action_id: Optional[str]
) -> None:
    """
    Create an entry in the user_logs table for "log" messages.

    Args:
        msg: The log message from the server
        user_id: User identifier
        user_action_id: ID of the user_action entry to reference
    """
    if not supabase_client.is_available():
        logger.debug("Supabase not available, skipping user log entry creation")
        return

    try:
        # Extract log information from the message
        session_id = msg.get("session_id")
        log_msg = msg.get("entry", "")
        success = msg.get("success")

        # Prepare data for user_logs table
        log_data = {"user_id": user_id, "session_id": session_id, "log_msg": log_msg}

        # Add success field if it's provided
        if success is not None:
            log_data["success"] = success

        # Add user_action_id if available (column might not exist in older schemas)
        if user_action_id is not None:
            log_data["user_action_id"] = user_action_id

        # Insert into user_logs table
        try:
            supabase_client.client.table("user_logs").insert(log_data).execute()
        except Exception as e:
            # If foreign key column doesn't exist, try without it
            if "user_action_id" in str(e) and "user_action_id" in log_data:
                log_data_no_fk = log_data.copy()
                del log_data_no_fk["user_action_id"]
                supabase_client.client.table("user_logs").insert(log_data_no_fk).execute()
                logger.debug(
                    f"User log entry created without foreign key for session: {session_id}"
                )
            else:
                raise e

        logger.debug(
            f"User log entry created for session: {session_id}, entry: '{log_msg[:50]}...'"
        )

    except Exception as e:
        logger.error(f"Failed to create user log entry for session {session_id}: {e}")
        logger.error(f"Log message was: '{log_msg[:100]}...'")
        logger.error(f"User action ID was: {user_action_id}")


def log_shim_control_registration(handshake: Dict[str, Any], session_id: str) -> None:
    """
    Log when a shim-control registers (user runs aco-launch script.py).

    Args:
        handshake: The handshake dictionary from the shim-control
        session_id: The assigned session ID
    """
    if not COLLECT_TELEMETRY:
        return

    if not supabase_client.is_available():
        logger.debug("Supabase not available, skipping shim-control registration logging")
        return

    try:
        user_id = get_user_id()

        # Create event data with relevant handshake information
        event_data = {
            "session_id": session_id,
            "cwd": handshake.get("cwd"),
            "command": handshake.get("command"),
            "environment": handshake.get("environment"),
            "name": handshake.get("name"),
            "prev_session_id": handshake.get("prev_session_id"),
            "is_rerun": handshake.get("prev_session_id") is not None,
        }

        response = (
            supabase_client.client.table("user_actions")
            .insert(
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "event_type": "shim_control_registration",
                    "event_data": json.dumps(event_data),
                }
            )
            .execute()
        )

        logger.debug(f"Shim-control registration logged to telemetry: {session_id}")

        # Get the user_action ID for code snapshot reference
        user_action_id = None
        if response.data and len(response.data) > 0:
            user_action_id = response.data[0].get("id")

        # Capture code snapshot for script launch
        project_root = handshake.get("cwd") or os.getcwd()
        store_code_snapshot_background(user_id, project_root, user_action_id)

        logger.debug(f"Code snapshot capture initiated for shim-control registration: {session_id}")

    except Exception as e:
        logger.error(f"Failed to log shim-control registration to telemetry: {e}")
