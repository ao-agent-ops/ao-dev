"""
PostgreSQL database backend for workflow experiments.
"""
import json
import dill
import psycopg2
import psycopg2.extras
import psycopg2.pool
import threading
import inspect
from urllib.parse import urlparse

from aco.common.logger import logger
from aco.common.constants import REMOTE_DATABASE_URL
from aco.common.utils import hash_input

# Global connection pool
_connection_pool = None


def _init_pool():
    """Initialize the connection pool if not already created"""
    global _connection_pool
    
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
    
    # Get caller information for debugging
    frame = inspect.currentframe()
    try:
        caller_frame = frame.f_back
        caller_function = caller_frame.f_code.co_name
        caller_file = caller_frame.f_code.co_filename.split('/')[-1]
        caller_line = caller_frame.f_lineno
    except:
        caller_function = "unknown"
        caller_file = "unknown"
        caller_line = 0
    finally:
        del frame
    
    thread_id = threading.get_ident()
    conn = _connection_pool.getconn()
    
    return conn


def return_conn(conn):
    """Return a connection to the pool"""
    if _connection_pool:
        # Get caller information for debugging
        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back
            caller_function = caller_frame.f_code.co_name
            caller_file = caller_frame.f_code.co_filename.split('/')[-1]
            caller_line = caller_frame.f_lineno
        except:
            caller_function = "unknown"
            caller_file = "unknown"
            caller_line = 0
        finally:
            del frame
        
        thread_id = threading.get_ident()
        _connection_pool.putconn(conn)


def close_all_connections():
    """Close all connections in the pool"""
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.debug("Closed PostgreSQL connection pool")


def _init_db(conn):
    """Initialize database schema (create tables if not exist)"""
    c = conn.cursor()
    
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
            input BYTEA,
            input_hash TEXT,
            input_overwrite BYTEA,
            output TEXT,
            color TEXT,
            label TEXT,
            api_type TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
    # Convert SQLite placeholders (?) to PostgreSQL placeholders (%s)
    sql = sql.replace("?", "%s")
    
    thread_id = threading.get_ident()
    logger.info(f"[QUERY_ONE] START thread={thread_id} sql={sql[:100]}...")
    
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute(sql, params)
        result = c.fetchone()
        logger.info(f"[QUERY_ONE] SUCCESS thread={thread_id} conn={id(conn)} result={'Found' if result else 'None'}")
        return result
    except Exception as e:
        logger.error(f"[QUERY_ONE] ERROR thread={thread_id} conn={id(conn)} error={e}")
        conn.rollback()
        raise
    finally:
        return_conn(conn)


def query_all(sql, params=()):
    """Execute a query and return all results"""
    # Convert SQLite placeholders (?) to PostgreSQL placeholders (%s)
    sql = sql.replace("?", "%s")
    
    thread_id = threading.get_ident()
    logger.info(f"[QUERY_ALL] START thread={thread_id} sql={sql[:100]}...")
    
    conn = get_conn()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        c.execute(sql, params)
        result = c.fetchall()
        logger.info(f"[QUERY_ALL] SUCCESS thread={thread_id} conn={id(conn)} rows={len(result)}")
        return result
    except Exception as e:
        logger.error(f"[QUERY_ALL] ERROR thread={thread_id} conn={id(conn)} error={e}")
        conn.rollback()
        raise
    finally:
        return_conn(conn)


def execute(sql, params=()):
    """Execute SQL statement"""
    # Convert SQLite placeholders (?) to PostgreSQL placeholders (%s)
    sql = sql.replace("?", "%s")
    
    thread_id = threading.get_ident()
    logger.info(f"[EXECUTE] START thread={thread_id} sql={sql[:100]}...")
    
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(sql, params)
        conn.commit()
        logger.info(f"[EXECUTE] SUCCESS thread={thread_id} conn={id(conn)}")
        return c.lastrowid if hasattr(c, 'lastrowid') else None
    except Exception as e:
        logger.error(f"[EXECUTE] ERROR thread={thread_id} conn={id(conn)} error={e}")
        conn.rollback()
        raise
    finally:
        return_conn(conn)


def deserialize_input(input_blob, api_type=None):
    """Deserialize input blob back to original dict"""
    if input_blob is None:
        return None
    # Postgres stores as bytes directly
    return dill.loads(bytes(input_blob))


def deserialize(output_json, api_type=None):
    """Deserialize output JSON back to response object"""
    if output_json is None:
        return None
    # Handle the case where dill pickled data was stored as TEXT
    # When binary data is stored as TEXT in PostgreSQL, we need to convert it back to bytes
    if isinstance(output_json, str):
        # Convert string back to bytes for dill.loads()
        output_json = output_json.encode('latin1')
    return dill.loads(output_json)


def store_taint_info(session_id, file_path, line_no, taint_nodes):
    """Store taint information for a line in a file"""
    file_id = f"{session_id}:{file_path}:{line_no}"
    content_hash = hash_input(f"{file_path}:{line_no}")
    taint_json = json.dumps(taint_nodes) if taint_nodes else "[]"

    logger.debug(f"Storing taint info for {file_id}: {taint_json}")

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
        logger.debug(f"Taint info for {file_path}:{line_no}: {row['taint']}")
        taint_nodes = json.loads(row["taint"]) if row["taint"] else []
        return row["session_id"], taint_nodes
    return None, []


def add_experiment_query(session_id, parent_session_id, name, default_graph, timestamp, cwd, command, env_json, default_success, default_note, default_log):
    """Execute PostgreSQL-specific INSERT for experiments table"""
    execute(
        """INSERT INTO experiments (session_id, parent_session_id, name, graph_topology, timestamp, cwd, command, environment, success, notes, log) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (session_id) DO UPDATE SET
               parent_session_id = EXCLUDED.parent_session_id,
               name = EXCLUDED.name,
               graph_topology = EXCLUDED.graph_topology,
               timestamp = EXCLUDED.timestamp,
               cwd = EXCLUDED.cwd,
               command = EXCLUDED.command,
               environment = EXCLUDED.environment,
               success = EXCLUDED.success,
               notes = EXCLUDED.notes,
               log = EXCLUDED.log""",
        (
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


def update_experiment_log_query(updated_log, updated_success, color_preview_json, graph_json, session_id):
    """Execute PostgreSQL-specific UPDATE for experiments log, success, color_preview, and graph_topology"""
    execute(
        "UPDATE experiments SET log=%s, success=%s, color_preview=%s, graph_topology=%s WHERE session_id=%s",
        (updated_log, updated_success, color_preview_json, graph_json, session_id),
    )