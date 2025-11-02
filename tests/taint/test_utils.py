"""Utility functions for taint tests."""


def cleanup_taint_db():
    """Clean up all taint information from the database and environment"""
    import os
    from aco.server.db import execute

    # Clear all taint records
    execute("DELETE FROM attachments")

    # Clean up environment variables that affect taint tracking
    if "AGENT_COPILOT_SESSION_ID" in os.environ:
        del os.environ["AGENT_COPILOT_SESSION_ID"]
