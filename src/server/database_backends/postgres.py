"""
PostgreSQL database backend for workflow experiments.
"""
import threading
import hashlib
import dill
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse

from aco.common.logger import logger
from aco.common.constants import DATABASE_URL


# Global lock for thread-safe database operations
_db_lock = threading.RLock()
_shared_conn = None


def get_conn():
    """Get the shared PostgreSQL connection, reconnecting if necessary"""
    global _shared_conn

    # Check if connection exists and is still alive
    if _shared_conn is not None:
        try:
            # Test if connection is still alive
            _shared_conn.isolation_level
        except (psycopg2.InterfaceError, psycopg2.OperationalError):
            logger.warning("PostgreSQL connection lost, reconnecting...")
            _shared_conn = None

    if _shared_conn is None:
        with _db_lock:
            # Double-check pattern to avoid race condition during initialization
            if _shared_conn is None:
                database_url = DATABASE_URL
                if not database_url:
                    raise ValueError(
                        "DATABASE_URL is required for Postgres connection (check config.yaml)"
                    )
                
                # Parse the connection string
                result = urlparse(database_url)
                
                # Connect to Postgres
                _shared_conn = psycopg2.connect(
                    host=result.hostname,
                    port=result.port or 5432,
                    user=result.username,
                    password=result.password,
                    database=result.path[1:],  # Remove leading '/'
                    connect_timeout=30,  # Increased timeout for remote connections
                )
                _shared_conn.autocommit = False
                
                _init_db(_shared_conn)
                logger.info(f"Initialized PostgreSQL connection to {result.hostname}")

    return _shared_conn


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
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with _db_lock:
                conn = get_conn()
                c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                c.execute(sql, params)
                result = c.fetchone()
                return result
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"Database connection error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                global _shared_conn
                _shared_conn = None  # Force reconnection
            else:
                raise


def query_all(sql, params=()):
    """Execute a query and return all results"""
    # Convert SQLite placeholders (?) to PostgreSQL placeholders (%s)
    sql = sql.replace("?", "%s")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with _db_lock:
                conn = get_conn()
                c = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                c.execute(sql, params)
                return c.fetchall()
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"Database connection error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                global _shared_conn
                _shared_conn = None  # Force reconnection
            else:
                raise


def execute(sql, params=()):
    """Execute SQL with proper locking to prevent transaction conflicts"""
    # Convert SQLite placeholders (?) to PostgreSQL placeholders (%s)
    sql = sql.replace("?", "%s")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with _db_lock:
                conn = get_conn()
                c = conn.cursor()
                c.execute(sql, params)
                conn.commit()
                return c.lastrowid if hasattr(c, 'lastrowid') else None
        except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
            logger.warning(f"Database connection error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                global _shared_conn
                _shared_conn = None  # Force reconnection
            else:
                raise


def hash_input(input_bytes):
    """Hash input for deduplication"""
    if isinstance(input_bytes, bytes):
        return hashlib.sha256(input_bytes).hexdigest()
    else:
        return hashlib.sha256(input_bytes.encode("utf-8")).hexdigest()


def deserialize_input(input_blob, api_type):
    """Deserialize input blob back to original dict"""
    if input_blob is None:
        return None
    # Postgres stores as bytes directly
    return dill.loads(bytes(input_blob))


def deserialize(output_json, api_type):
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
    import json

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
    import json

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