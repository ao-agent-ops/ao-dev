"""
PostgreSQL database backend for workflow experiments.
"""

import json
import psycopg2
import psycopg2.extras
import psycopg2.pool
import threading
from urllib.parse import urlparse

from ao.common.logger import logger
from ao.common.constants import REMOTE_DATABASE_URL
from ao.common.utils import hash_input

# Global connection pool
_connection_pool = None
_pool_lock = threading.Lock()


def _init_pool():
    """Initialize the connection pool if not already created"""
    global _connection_pool

    with _pool_lock:
        if _connection_pool is None:
            database_url = REMOTE_DATABASE_URL
            if not database_url:
                raise ValueError(
                    "REMOTE_DATABASE_URL is required for Postgres connection (check config.yaml)"
                )

            # Parse the connection string
            result = urlparse(database_url)

            # Create connection pool (1 min, 4 max connections to support concurrent access)
            _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=4,
                host=result.hostname,
                port=result.port or 5432,
                user=result.username,
                password=result.password,
                database=result.path[1:],  # Remove leading '/'
                connect_timeout=30,
            )

            # Initialize database schema using a connection from the pool
            conn = _connection_pool.getconn()
            try:
                _init_db(conn)
                logger.info(f"Initialized PostgreSQL connection pool to {result.hostname}")
            finally:
                _connection_pool.putconn(conn)


def get_conn():
    """Get a connection from the pool"""
    _init_pool()

    # Check if pool exists before trying to get connection
    if not _connection_pool:
        raise RuntimeError("Connection pool is not available")

    try:
        conn = _connection_pool.getconn()
    except Exception as e:
        logger.error(f"Failed to get connection from pool: {e}")
        raise

    return conn


def return_conn(conn):
    """Return a connection to the pool"""
    try:
        _connection_pool.putconn(conn)
    except Exception as e:
        # Pool might have been closed, just close the connection directly
        logger.warning(f"Failed to return connection to pool (pool might be closed): {e}")
        try:
            conn.close()
        except:
            pass


def close_all_connections():
    """Close all connections in the pool"""
    global _connection_pool
    with _pool_lock:
        if _connection_pool:
            try:
                _connection_pool.closeall()
            except Exception as e:
                logger.warning(f"Error closing connection pool: {e}")
            finally:
                _connection_pool = None
            logger.debug("Closed PostgreSQL connection pool")


def clear_connections():
    """Clear cached connections to force reconnection (alias for close_all_connections)."""
    close_all_connections()


def _init_db(conn):
    """Initialize database schema (create tables if not exist)"""
    c = conn.cursor()

    # Create users table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            google_id VARCHAR(255) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            picture TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create experiments table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            session_id TEXT PRIMARY KEY,
            parent_session_id TEXT,
            graph_topology TEXT,
            color_preview TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cwd TEXT,
            command TEXT,
            environment TEXT,
            version_date TEXT,
            name TEXT,
            success TEXT CHECK (success IN ('', 'Satisfactory', 'Failed')),
            notes TEXT,
            log TEXT,
            user_id INTEGER,
            FOREIGN KEY (parent_session_id) REFERENCES experiments (session_id),
            UNIQUE (parent_session_id, name)
        )
    """
    )

    # Create llm_calls table
    # HACK: Renove foreign key constrain bc parallel inserts experiment and llm calls.
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_calls (
            session_id TEXT,
            node_id TEXT,
            input TEXT,
            input_hash TEXT,
            input_overwrite TEXT,
            output TEXT,
            color TEXT,
            label TEXT,
            api_type TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (session_id, node_id)
        )
    """
    )

    # Create attachments table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS attachments (
            file_id TEXT PRIMARY KEY,
            session_id TEXT,
            line_no INTEGER,
            content_hash TEXT,
            file_path TEXT,
            taint TEXT,
            FOREIGN KEY (session_id) REFERENCES experiments (session_id)
        )
    """
    )
    # Create indexes
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
    logger.debug("Database schema initialized")


def query_one(sql, params=()):
    """Execute a query and return one result"""
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute(sql, params)
        result = c.fetchone()
        return result
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
        # Connection died - don't try to rollback, just close it
        logger.warning(f"Connection died during query_one: {e}")
        try:
            conn.close()
        except:
            pass
        raise
    except Exception as e:
        # Other errors - try to rollback
        try:
            conn.rollback()
        except:
            pass
        raise
    finally:
        return_conn(conn)


def query_all(sql, params=()):
    """Execute a query and return all results"""
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute(sql, params)
        result = c.fetchall()
        return result
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
        # Connection died - don't try to rollback, just close it
        logger.warning(f"Connection died during query_all: {e}")
        try:
            conn.close()
        except:
            pass
        raise
    except Exception as e:
        # Other errors - try to rollback
        try:
            conn.rollback()
        except:
            pass
        raise
    finally:
        return_conn(conn)


def execute(sql, params=()):
    """Execute SQL statement"""
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(sql, params)
        conn.commit()
        return c.lastrowid if hasattr(c, "lastrowid") else None
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
        # Connection died - don't try to rollback, just close it
        logger.warning(f"Connection died during execute: {e}")
        try:
            conn.close()
        except:
            pass
        raise
    except Exception as e:
        # Other errors - try to rollback
        try:
            conn.rollback()
        except:
            pass
        raise
    finally:
        return_conn(conn)


def store_taint_info(session_id, file_path, line_no, taint_nodes):
    """Store taint information for a line in a file"""
    file_id = f"{session_id}:{file_path}:{line_no}"
    content_hash = hash_input(f"{file_path}:{line_no}")
    taint_json = json.dumps(taint_nodes) if taint_nodes else "[]"

    execute(
        """
        INSERT INTO attachments (file_id, session_id, line_no, content_hash, file_path, taint)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (file_id) DO UPDATE SET
            session_id = EXCLUDED.session_id,
            line_no = EXCLUDED.line_no,
            content_hash = EXCLUDED.content_hash,
            file_path = EXCLUDED.file_path,
            taint = EXCLUDED.taint
        """,
        (file_id, session_id, line_no, content_hash, file_path, taint_json),
    )


def get_taint_info(file_path, line_no):
    """Get taint information for a specific line in a file from any previous session"""
    row = query_one(
        """
        SELECT session_id, taint FROM attachments 
        WHERE file_path = %s AND line_no = %s
        ORDER BY ctid DESC
        LIMIT 1
        """,
        (file_path, line_no),
    )
    if row:
        taint_nodes = json.loads(row["taint"]) if row["taint"] else []
        return row["session_id"], taint_nodes
    return None, []


def add_experiment_query(
    session_id,
    parent_session_id,
    name,
    default_graph,
    timestamp,
    cwd,
    command,
    env_json,
    default_success,
    default_note,
    default_log,
    user_id,
    version_date,
):
    """Execute PostgreSQL-specific INSERT for experiments table"""
    execute(
        """INSERT INTO experiments (session_id, parent_session_id, name, graph_topology, timestamp, cwd, command, environment, version_date, success, notes, log, user_id) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (session_id) DO UPDATE SET
               parent_session_id = EXCLUDED.parent_session_id,
               name = EXCLUDED.name,
               graph_topology = EXCLUDED.graph_topology,
               timestamp = EXCLUDED.timestamp,
               cwd = EXCLUDED.cwd,
               command = EXCLUDED.command,
               environment = EXCLUDED.environment,
               version_date = EXCLUDED.version_date,
               success = EXCLUDED.success,
               notes = EXCLUDED.notes,
               log = EXCLUDED.log,
               user_id = EXCLUDED.user_id""",
        (
            session_id,
            parent_session_id,
            name,
            default_graph,
            timestamp,
            cwd,
            command,
            env_json,
            version_date,
            default_success,
            default_note,
            default_log,
            user_id,
        ),
    )


def set_input_overwrite_query(input_overwrite, session_id, node_id):
    """Execute PostgreSQL-specific UPDATE for llm_calls input_overwrite"""
    execute(
        "UPDATE llm_calls SET input_overwrite=%s, output=NULL WHERE session_id=%s AND node_id=%s",
        (input_overwrite, session_id, node_id),
    )


def set_output_overwrite_query(output_overwrite, session_id, node_id):
    """Execute PostgreSQL-specific UPDATE for llm_calls output"""
    execute(
        "UPDATE llm_calls SET output=%s WHERE session_id=%s AND node_id=%s",
        (output_overwrite, session_id, node_id),
    )


def update_experiment_graph_topology_query(graph_json, session_id):
    """Execute PostgreSQL-specific UPDATE for experiments graph_topology"""
    execute(
        "UPDATE experiments SET graph_topology=%s WHERE session_id=%s", (graph_json, session_id)
    )


def update_experiment_timestamp_query(timestamp, session_id):
    """Execute PostgreSQL-specific UPDATE for experiments timestamp"""
    execute("UPDATE experiments SET timestamp=%s WHERE session_id=%s", (timestamp, session_id))


def update_experiment_name_query(run_name, session_id):
    """Execute PostgreSQL-specific UPDATE for experiments name"""
    execute(
        "UPDATE experiments SET name=%s WHERE session_id=%s",
        (run_name, session_id),
    )


def update_experiment_result_query(result, session_id):
    """Execute PostgreSQL-specific UPDATE for experiments success"""
    execute(
        "UPDATE experiments SET success=%s WHERE session_id=%s",
        (result, session_id),
    )


def update_experiment_notes_query(notes, session_id):
    """Execute PostgreSQL-specific UPDATE for experiments notes"""
    execute(
        "UPDATE experiments SET notes=%s WHERE session_id=%s",
        (notes, session_id),
    )


def update_experiment_command_query(command, session_id):
    """Execute PostgreSQL-specific UPDATE for experiments command"""
    execute(
        "UPDATE experiments SET command=%s WHERE session_id=%s",
        (command, session_id),
    )


def update_experiment_log_query(
    updated_log, updated_success, color_preview_json, graph_json, session_id
):
    """Execute PostgreSQL-specific UPDATE for experiments log, success, color_preview, and graph_topology"""
    execute(
        "UPDATE experiments SET log=%s, success=%s, color_preview=%s, graph_topology=%s WHERE session_id=%s",
        (updated_log, updated_success, color_preview_json, graph_json, session_id),
    )


# Attachment-related queries
def check_attachment_exists_query(file_id):
    """Check if attachment with given file_id exists."""
    return query_one("SELECT file_id FROM attachments WHERE file_id=%s", (file_id,))


def get_attachment_by_content_hash_query(content_hash):
    """Get attachment file path by content hash."""
    return query_one("SELECT file_path FROM attachments WHERE content_hash=%s", (content_hash,))


def insert_attachment_query(file_id, content_hash, file_path):
    """Insert new attachment record."""
    execute(
        "INSERT INTO attachments (file_id, content_hash, file_path) VALUES (%s, %s, %s)",
        (file_id, content_hash, file_path),
    )


def get_attachment_file_path_query(file_id):
    """Get file path for attachment by file_id."""
    return query_one("SELECT file_path FROM attachments WHERE file_id=%s", (file_id,))


# Subrun queries
def get_subrun_by_parent_and_name_query(parent_session_id, name):
    """Get subrun session_id by parent session and name."""
    return query_one(
        "SELECT session_id FROM experiments WHERE parent_session_id = %s AND name = %s",
        (parent_session_id, name),
    )


def get_parent_session_id_query(session_id):
    """Get parent session ID for a given session."""
    return query_one("SELECT parent_session_id FROM experiments WHERE session_id=%s", (session_id,))


# LLM calls queries
def get_llm_call_by_session_and_hash_query(session_id, input_hash):
    """Get LLM call by session_id and input_hash."""
    return query_one(
        "SELECT node_id, input_overwrite, output FROM llm_calls WHERE session_id=%s AND input_hash=%s",
        (session_id, input_hash),
    )


def insert_llm_call_with_output_query(
    session_id, input_pickle, input_hash, node_id, api_type, output_pickle
):
    """Insert new LLM call record with output in a single operation (upsert)."""
    execute(
        """
        INSERT INTO llm_calls (session_id, input, input_hash, node_id, api_type, output) 
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (session_id, node_id) 
        DO UPDATE SET output = EXCLUDED.output
        """,
        (session_id, input_pickle, input_hash, node_id, api_type, output_pickle),
    )


# Experiment list and graph queries
def get_finished_runs_query():
    """Get all finished runs ordered by timestamp."""
    return query_all("SELECT session_id, timestamp FROM experiments ORDER BY timestamp DESC", ())


def get_all_experiments_sorted_by_user_query(user_id=None):
    # If user_id is None, because user not logged in and UI requested experiment list, send nothing
    if user_id is None:
        return []

    """Get all experiments sorted by timestamp desc, optionally filtered by user_id."""
    # Filter by user_id
    return query_all(
        "SELECT session_id, timestamp, color_preview, name, version_date, success, notes, log FROM experiments WHERE user_id=%s ORDER BY timestamp DESC",
        (user_id,),
    )


def get_experiment_graph_topology_query(session_id):
    """Get graph topology for an experiment."""
    return query_one("SELECT graph_topology FROM experiments WHERE session_id=%s", (session_id,))


def get_experiment_color_preview_query(session_id):
    """Get color preview for an experiment."""
    return query_one("SELECT color_preview FROM experiments WHERE session_id=%s", (session_id,))


def get_experiment_environment_query(parent_session_id):
    """Get experiment cwd, command, and environment."""
    return query_one(
        "SELECT cwd, command, environment FROM experiments WHERE session_id=%s",
        (parent_session_id,),
    )


def update_experiment_color_preview_query(color_preview_json, session_id):
    """Update experiment color preview."""
    execute(
        "UPDATE experiments SET color_preview=%s WHERE session_id=%s",
        (color_preview_json, session_id),
    )


def get_experiment_exec_info_query(session_id):
    """Get experiment execution info (cwd, command, environment)."""
    return query_one(
        "SELECT cwd, command, environment FROM experiments WHERE session_id=%s", (session_id,)
    )


# Database cleanup queries
def delete_all_experiments_query():
    """Delete all records from experiments table."""
    execute("DELETE FROM experiments")


def delete_all_llm_calls_query():
    """Delete all records from llm_calls table."""
    execute("DELETE FROM llm_calls")


def delete_llm_calls_query(session_id):
    """Delete all llm calls belonging to a session id."""
    execute("DELETE FROM llm_calls WHERE session_id=?", (session_id,))


def get_session_name_query(session_id):
    """Get session name by session_id."""
    return query_one("SELECT name FROM experiments WHERE session_id=%s", (session_id,))


def get_llm_call_input_api_type_query(session_id, node_id):
    """Get input and api_type from llm_calls by session_id and node_id."""
    return query_one(
        "SELECT input, api_type FROM llm_calls WHERE session_id=%s AND node_id=%s",
        (session_id, node_id),
    )


def get_llm_call_output_api_type_query(session_id, node_id):
    """Get output and api_type from llm_calls by session_id and node_id."""
    return query_one(
        "SELECT output, api_type FROM llm_calls WHERE session_id=%s AND node_id=%s",
        (session_id, node_id),
    )


def get_experiment_log_success_graph_query(session_id):
    """Get log, success, and graph_topology from experiments by session_id."""
    return query_one(
        "SELECT log, success, graph_topology FROM experiments WHERE session_id=%s",
        (session_id,),
    )


def upsert_user(google_id, email, name, picture):
    """
    Upsert user - insert if not exists, update if exists.

    Includes retry logic to handle connection closures (e.g., from database mode switching).

    Args:
        google_id: Google OAuth ID
        email: User email
        name: User name
        picture: User profile picture URL

    Returns:
        The user record after upsert
    """
    max_retries = 3
    for attempt in range(max_retries):
        conn = None
        try:
            conn = get_conn()
            c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # Check if user exists
            c.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
            existing = c.fetchone()

            if existing:
                # Update existing user
                c.execute(
                    "UPDATE users SET name = %s, picture = %s, updated_at = CURRENT_TIMESTAMP WHERE google_id = %s",
                    (name, picture, google_id),
                )
            else:
                # Insert new user
                c.execute(
                    "INSERT INTO users (google_id, email, name, picture, created_at, updated_at) "
                    "VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                    (google_id, email, name, picture),
                )

            # Commit the transaction
            conn.commit()

            # Return the user record
            c.execute("SELECT * FROM users WHERE google_id = %s", (google_id,))
            result = c.fetchone()
            return result

        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            # Connection was closed - retry
            if attempt < max_retries - 1:
                logger.warning(
                    f"Connection closed during upsert, retrying ({attempt + 1}/{max_retries}): {e}"
                )
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
                continue
            else:
                raise
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                return_conn(conn)


def get_user_by_id_query(user_id):
    """
    Get user by their ID.

    Args:
        user_id: The user's ID

    Returns:
        The user record or None if not found
    """
    return query_one("SELECT * FROM users WHERE id = %s", (user_id,))


def get_next_run_index_query():
    """Get the next run index based on how many runs already exist."""
    row = query_one("SELECT COUNT(*) as count FROM experiments", ())
    if row:
        return row["count"] + 1
    return 1
