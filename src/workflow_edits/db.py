import os
import sqlite3
import threading
import hashlib

import dill
from common.logger import logger
from common.constants import ACO_DB_PATH
from runtime_tracing.taint_wrappers import untaint_if_needed


# Global lock among concurrent threads: Threads within a process share a single
# DB connection, so they cannot issue DB operations in parallel. Python releases
# the GIL during DB operations, so we use a global lock to ensure only one thread
# executes a DB operation at a time. Different processes use different connections
# and SQLite handles concurrency amongst them.
# NOTE: Alternatively, we can give each thread its own connection and avoid the
# global lock. This would improve scalability, which might be important for the
# server (e.g., 1000s of parallel production runs). However, we need to switch
# away from SQLite and make larger refactors for that anyways, so we currently
# stick with this strawman approach.
_db_lock = threading.RLock()
_shared_conn = None


def get_conn():
    """Get the shared SQLite connection"""
    global _shared_conn

    if _shared_conn is None:
        with _db_lock:
            # Double-check pattern to avoid race condition during initialization
            if _shared_conn is None:
                db_path = os.path.join(ACO_DB_PATH, "experiments.sqlite")
                _shared_conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
                _shared_conn.row_factory = sqlite3.Row
                # Enable WAL mode for better concurrent access
                _shared_conn.execute("PRAGMA journal_mode=WAL")
                _shared_conn.execute("PRAGMA synchronous=NORMAL")
                _shared_conn.execute("PRAGMA busy_timeout=10000")  # 10 second timeout
                _init_db(_shared_conn)
                logger.debug(f"Initialized shared DB connection at {db_path}")

    return _shared_conn


def _init_db(conn):
    c = conn.cursor()
    # Create experiments table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            session_id TEXT PRIMARY KEY,
            parent_session_id TEXT,
            graph_topology TEXT,
            color_preview TEXT,
            timestamp TEXT DEFAULT (datetime('now')),
            cwd TEXT,
            command TEXT,
            environment TEXT,
            code_hash TEXT,
            name TEXT,
            success TEXT CHECK (success IN ('', 'Satisfactory', 'Failed')),
            notes TEXT,
            log TEXT,
            FOREIGN KEY (parent_session_id) REFERENCES experiments (session_id),
            UNIQUE (parent_session_id, name)
        )
    """
    )
    # Create llm_calls table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_calls (
            session_id TEXT,
            node_id TEXT,
            input BLOB,
            input_hash TEXT,
            input_overwrite BLOB,
            output TEXT,
            color TEXT,
            label TEXT,
            api_type TEXT,
            timestamp TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (session_id, node_id),
            FOREIGN KEY (session_id) REFERENCES experiments (session_id)
        )
    """
    )
    # Create attachments table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS attachments (
            file_id TEXT PRIMARY KEY,
            content_hash TEXT,
            file_path TEXT
        )
    """
    )
    c.execute(
        """
        CREATE INDEX IF NOT EXISTS attachments_content_hash_idx ON attachments(content_hash)
    """
    )
    c.execute(
        """
        CREATE INDEX IF NOT EXISTS original_input_lookup ON llm_calls(session_id, input_hash)
    """
    )
    c.execute(
        """
        CREATE INDEX IF NOT EXISTS experiments_timestamp_idx ON experiments(timestamp DESC)
    """
    )
    conn.commit()


def query_one(sql, params=()):
    with _db_lock:
        conn = get_conn()
        c = conn.cursor()
        c.execute(sql, params)
        return c.fetchone()


def query_all(sql, params=()):
    with _db_lock:
        conn = get_conn()
        c = conn.cursor()
        c.execute(sql, params)
        return c.fetchall()


def execute(sql, params=()):
    """Execute SQL with proper locking to prevent transaction conflicts"""
    with _db_lock:
        conn = get_conn()
        c = conn.cursor()
        c.execute(sql, params)
        conn.commit()
        return c.lastrowid


def hash_input(input_bytes):
    if isinstance(input_bytes, bytes):
        return hashlib.sha256(input_bytes).hexdigest()
    else:
        return hashlib.sha256(input_bytes.encode("utf-8")).hexdigest()


def deserialize_input(input_blob, api_type):
    """Deserialize input blob back to original dict"""
    if input_blob is None:
        return None
    return dill.loads(input_blob)


def deserialize(output_json, api_type):
    """Deserialize output JSON back to response object"""
    if output_json is None:
        return None
    # This would need to be implemented based on api_type
    # For now, just return the JSON string
    return output_json
