import json
from typing import Dict, Any, Optional
from common.logger import logger
from telemetry.client import supabase_client


def log_user_actions(
    user_id: str, event_type: str, event_data: Dict[str, Any], session_id: Optional[str] = None
) -> Optional[str]:
    """Log a UI interaction event to Supabase and return the event ID."""
    if not supabase_client.is_available():
        logger.debug("Supabase not available, skipping UI event logging")
        return None

    try:
        response = (
            supabase_client.client.table("user_actions")
            .insert(
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "event_type": event_type,
                    "event_data": json.dumps(event_data),
                }
            )
            .execute()
        )

        logger.debug(f"UI event logged: {event_type}")

        # Return the ID of the inserted event
        if response.data and len(response.data) > 0:
            return response.data[0].get("id")
        return None

    except Exception as e:
        logger.error(f"Failed to log UI event: {e}")
        return None


def log_experiment_click(user_id: str, session_id: str, experiment_name: str) -> Optional[str]:
    """Log when user clicks on an experiment card and return the event ID."""
    return log_user_actions(
        user_id=user_id,
        session_id=session_id,
        event_type="experiment_click",
        event_data={"experiment_name": experiment_name},
    )


def log_node_click(
    user_id: str, session_id: str, node_id: str, node_type: str = ""
) -> Optional[str]:
    """Log when user clicks on a graph node and return the event ID."""
    return log_user_actions(
        user_id=user_id,
        session_id=session_id,
        event_type="node_click",
        event_data={"node_id": node_id, "node_type": node_type},
    )


def log_node_edit(
    user_id: str,
    session_id: str,
    node_id: str,
    field: str,
    old_value: str = "",
    new_value: str = "",
) -> Optional[str]:
    """Log when user edits a node and return the event ID."""
    return log_user_actions(
        user_id=user_id,
        session_id=session_id,
        event_type="node_edit",
        event_data={
            "node_id": node_id,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        },
    )


def log_experiment_rerun(user_id: str, session_id: str, experiment_name: str = "") -> Optional[str]:
    """Log when user triggers an experiment rerun and return the event ID."""
    return log_user_actions(
        user_id=user_id,
        session_id=session_id,
        event_type="experiment_rerun",
        event_data={"experiment_name": experiment_name, "action": "rerun_experiment"},
    )


def store_user_log(
    user_id: str, session_id: str, log_msg: str, success: Optional[bool] = None
) -> bool:
    """Store a user log entry to Supabase."""
    if not supabase_client.is_available():
        logger.debug("Supabase not available, skipping user log storage")
        return False

    try:
        data = {
            "user_id": user_id,
            "session_id": session_id,
            "log_msg": log_msg,
        }
        if success is not None:
            data["success"] = success

        supabase_client.client.table("user_logs").insert(data).execute()
        logger.debug(f"User log stored: {log_msg[:50]}...")
        return True

    except Exception as e:
        logger.error(f"Failed to store user log: {e}")
        return False


if __name__ == "__main__":
    print("Testing UI events functionality...")

    test_user = "test_user_123"
    test_session = "test_session_456"

    print("\n1. Testing experiment click logging...")
    success = log_experiment_click(test_user, test_session, "my_test_experiment")
    if success:
        print("✅ Experiment click logged successfully!")
    else:
        print("❌ Experiment click logging failed")

    print("\n2. Testing node click logging...")
    success = log_node_click(test_user, test_session, "node_789", "llm_call")
    if success:
        print("✅ Node click logged successfully!")
    else:
        print("❌ Node click logging failed")

    print("\n3. Testing node edit logging...")
    success = log_node_edit(
        test_user, test_session, "node_789", "input", "old prompt text", "new prompt text"
    )
    if success:
        print("✅ Node edit logged successfully!")
    else:
        print("❌ Node edit logging failed")

    print("\n4. Testing custom event logging...")
    success = log_user_actions(
        test_user,
        "custom_action",
        {"button": "save", "timestamp": "2024-01-01T10:00:00Z"},
        test_session,
    )
    if success:
        print("✅ Custom event logged successfully!")
    else:
        print("❌ Custom event logging failed")

    print("\n5. Testing user log storage...")
    success = store_user_log(test_user, test_session, "Test log entry from user", True)
    if success:
        print("✅ User log stored successfully!")
    else:
        print("❌ User log storage failed")

    print("\nAll telemetry tests completed!")
