"""
Database manager for handling dynamic switching between SQLite and PostgreSQL backends.

This module provides a unified interface for database operations while supporting
runtime switching between local SQLite and remote PostgreSQL databases.
"""

from aco.common.logger import logger


class DatabaseManager:
    """
    Manages database backend selection and routes operations to appropriate backend.

    Supports switching between:
    - Local mode: SQLite database for local development
    - Remote mode: PostgreSQL database for shared/production use
    """

    def __init__(self):
        """Initialize with default SQLite backend."""
        # Default to SQLite, user can switch via UI dropdown
        self.backend = "sqlite"

        # Lazy-loaded backend modules
        self._sqlite_module = None
        self._postgres_module = None

        logger.info(f"DatabaseManager initialized with backend: {self.get_current_mode()}")

    def _get_backend_module(self):
        """
        Lazy load and return the appropriate backend module.

        Returns:
            Backend module (sqlite or postgres) with database functions
        """
        if self.backend == "sqlite":
            if self._sqlite_module is None:
                from aco.server.database_backends import sqlite

                self._sqlite_module = sqlite
                logger.debug("Loaded SQLite backend module")
            return self._sqlite_module
        else:
            if self._postgres_module is None:
                from aco.server.database_backends import postgres

                self._postgres_module = postgres
                logger.debug("Loaded PostgreSQL backend module")
            return self._postgres_module

    def switch_mode(self, mode: str):
        """
        Switch between 'local' (SQLite) and 'remote' (PostgreSQL) database modes.

        Args:
            mode: Either 'local' for SQLite or 'remote' for PostgreSQL

        Raises:
            ValueError: If mode is not 'local' or 'remote'
        """
        if mode == "local":
            self.backend = "sqlite"
            logger.info("Switched to local SQLite database")
        elif mode == "remote":
            from aco.common.constants import REMOTE_DATABASE_URL

            self.backend = REMOTE_DATABASE_URL
            logger.info("Switched to remote PostgreSQL database")
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'local' or 'remote'")

        # Clear cached connections to force reconnection with new backend
        self._clear_backend_connections()

    def _clear_backend_connections(self):
        """Clear cached connections in both backends to force reconnection."""
        if self._sqlite_module:
            self._sqlite_module._shared_conn = None
            logger.debug("Cleared SQLite connection cache")
        if self._postgres_module:
            # Close the connection pool to force fresh connections
            self._postgres_module.close_all_connections()
            logger.debug("Cleared PostgreSQL connection pool")

    def get_current_mode(self) -> str:
        """
        Get the current database mode.

        Returns:
            'local' if using SQLite, 'remote' if using PostgreSQL
        """
        return "local" if self.backend == "sqlite" else "remote"

    # Database operation routing methods
    # All methods delegate to the appropriate backend module

    def query_one(self, query, params=None):
        """Execute query and return single row result."""
        backend = self._get_backend_module()
        return backend.query_one(query, params or ())

    def query_all(self, query, params=None):
        """Execute query and return all rows."""
        backend = self._get_backend_module()
        return backend.query_all(query, params or ())

    def execute(self, query, params=None):
        """Execute query without returning results."""
        backend = self._get_backend_module()
        return backend.execute(query, params or ())

    # def get_conn(self):
    #     """Get database connection."""
    #     backend = self._get_backend_module()
    #     return backend.get_conn()

    def deserialize_input(self, data):
        """Deserialize input data."""
        backend = self._get_backend_module()
        return backend.deserialize_input(data)

    def deserialize(self, data):
        """Deserialize data."""
        backend = self._get_backend_module()
        return backend.deserialize(data)

    def store_taint_info(self, session_id, file_path, line_number, taint_nodes):
        """Store taint tracking information."""
        backend = self._get_backend_module()
        return backend.store_taint_info(session_id, file_path, line_number, taint_nodes)

    def get_taint_info(self, file_path, line_number):
        """Retrieve taint tracking information."""
        backend = self._get_backend_module()
        return backend.get_taint_info(file_path, line_number)

    def add_experiment_query(
        self,
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
    ):
        """Add experiment to database using backend-specific SQL syntax."""
        backend = self._get_backend_module()
        return backend.add_experiment_query(
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
        )

    def set_input_overwrite_query(self, input_overwrite, session_id, node_id):
        """Update llm_calls input_overwrite using backend-specific SQL syntax."""
        backend = self._get_backend_module()
        return backend.set_input_overwrite_query(input_overwrite, session_id, node_id)

    def set_output_overwrite_query(self, output_overwrite, session_id, node_id):
        """Update llm_calls output using backend-specific SQL syntax."""
        backend = self._get_backend_module()
        return backend.set_output_overwrite_query(output_overwrite, session_id, node_id)

    def update_experiment_graph_topology_query(self, graph_json, session_id):
        """Update experiments graph_topology using backend-specific SQL syntax."""
        backend = self._get_backend_module()
        return backend.update_experiment_graph_topology_query(graph_json, session_id)

    def update_experiment_timestamp_query(self, timestamp, session_id):
        """Update experiments timestamp using backend-specific SQL syntax."""
        backend = self._get_backend_module()
        return backend.update_experiment_timestamp_query(timestamp, session_id)

    def update_experiment_name_query(self, run_name, session_id):
        """Update experiments name using backend-specific SQL syntax."""
        backend = self._get_backend_module()
        return backend.update_experiment_name_query(run_name, session_id)

    def update_experiment_result_query(self, result, session_id):
        """Update experiments success using backend-specific SQL syntax."""
        backend = self._get_backend_module()
        return backend.update_experiment_result_query(result, session_id)

    def update_experiment_notes_query(self, notes, session_id):
        """Update experiments notes using backend-specific SQL syntax."""
        backend = self._get_backend_module()
        return backend.update_experiment_notes_query(notes, session_id)

    def update_experiment_log_query(
        self, updated_log, updated_success, color_preview_json, graph_json, session_id
    ):
        """Update experiments log, success, color_preview, and graph_topology using backend-specific SQL syntax."""
        backend = self._get_backend_module()
        return backend.update_experiment_log_query(
            updated_log, updated_success, color_preview_json, graph_json, session_id
        )

    # Attachment-related queries
    def check_attachment_exists_query(self, file_id):
        """Check if attachment with given file_id exists."""
        backend = self._get_backend_module()
        return backend.check_attachment_exists_query(file_id)

    def get_attachment_by_content_hash_query(self, content_hash):
        """Get attachment file path by content hash."""
        backend = self._get_backend_module()
        return backend.get_attachment_by_content_hash_query(content_hash)

    def insert_attachment_query(self, file_id, content_hash, file_path):
        """Insert new attachment record."""
        backend = self._get_backend_module()
        return backend.insert_attachment_query(file_id, content_hash, file_path)

    def get_attachment_file_path_query(self, file_id):
        """Get file path for attachment by file_id."""
        backend = self._get_backend_module()
        return backend.get_attachment_file_path_query(file_id)

    # Subrun queries
    def get_subrun_by_parent_and_name_query(self, parent_session_id, name):
        """Get subrun session_id by parent session and name."""
        backend = self._get_backend_module()
        return backend.get_subrun_by_parent_and_name_query(parent_session_id, name)

    def get_parent_session_id_query(self, session_id):
        """Get parent session ID for a given session."""
        backend = self._get_backend_module()
        return backend.get_parent_session_id_query(session_id)

    # LLM calls queries
    def get_llm_call_by_session_and_hash_query(self, session_id, input_hash):
        """Get LLM call by session_id and input_hash."""
        backend = self._get_backend_module()
        return backend.get_llm_call_by_session_and_hash_query(session_id, input_hash)

    def insert_llm_call_with_output_query(
        self, session_id, input_pickle, input_hash, node_id, api_type, output_pickle
    ):
        """Insert new LLM call record with output in a single operation."""
        backend = self._get_backend_module()
        return backend.insert_llm_call_with_output_query(
            session_id, input_pickle, input_hash, node_id, api_type, output_pickle
        )

    # Experiment list and graph queries
    def get_finished_runs_query(self):
        """Get all finished runs ordered by timestamp."""
        backend = self._get_backend_module()
        return backend.get_finished_runs_query()

    # def get_all_experiments_sorted_query(self):
    #     """Get all experiments sorted by timestamp desc."""
    #     backend = self._get_backend_module()
    #     return backend.get_all_experiments_sorted_query()

    def get_all_experiments_sorted_by_user_query(self, user_id):
        """Get all experiments sorted by timestamp desc, optionally filtered by user_id."""
        backend = self._get_backend_module()
        return backend.get_all_experiments_sorted_by_user_query(user_id)

    def get_experiment_graph_topology_query(self, session_id):
        """Get graph topology for an experiment."""
        backend = self._get_backend_module()
        return backend.get_experiment_graph_topology_query(session_id)

    def get_experiment_color_preview_query(self, session_id):
        """Get color preview for an experiment."""
        backend = self._get_backend_module()
        return backend.get_experiment_color_preview_query(session_id)

    def get_experiment_environment_query(self, parent_session_id):
        """Get experiment cwd, command, and environment."""
        backend = self._get_backend_module()
        return backend.get_experiment_environment_query(parent_session_id)

    def update_experiment_color_preview_query(self, color_preview_json, session_id):
        """Update experiment color preview."""
        backend = self._get_backend_module()
        return backend.update_experiment_color_preview_query(color_preview_json, session_id)

    def get_experiment_exec_info_query(self, session_id):
        """Get experiment execution info (cwd, command, environment)."""
        backend = self._get_backend_module()
        return backend.get_experiment_exec_info_query(session_id)

    # Database cleanup queries
    def delete_all_experiments_query(self):
        """Delete all records from experiments table."""
        backend = self._get_backend_module()
        return backend.delete_all_experiments_query()

    def delete_all_llm_calls_query(self):
        """Delete all records from llm_calls table."""
        backend = self._get_backend_module()
        return backend.delete_all_llm_calls_query()

    def get_session_name_query(self, session_id):
        """Get session name by session_id."""
        backend = self._get_backend_module()
        return backend.get_session_name_query(session_id)

        # Embedding-related queries (lessons_embeddings)

    def insert_lesson_embedding_query(
        self, session_id: str, node_id: str, embedding_json: str, user_id: int = None
    ):
        """
        Insert or replace an embedding for (session_id, node_id).

        Note: currently only implemented for the SQLite backend.
        """
        backend = self._get_backend_module()
        if not hasattr(backend, "insert_lesson_embedding_query"):
            raise NotImplementedError(
                "insert_lesson_embedding_query not implemented for this backend"
            )
        return backend.insert_lesson_embedding_query(session_id, node_id, embedding_json, user_id)

    def get_lesson_embedding_query(self, session_id: str, node_id: str):
        """
        Fetch embedding row for (session_id, node_id).
        """
        backend = self._get_backend_module()
        if not hasattr(backend, "get_lesson_embedding_query"):
            raise NotImplementedError("get_lesson_embedding_query not implemented for this backend")
        return backend.get_lesson_embedding_query(session_id, node_id)

    def get_all_lesson_embeddings_except_query(self, session_id: str, node_id: str):
        """
        Fetch all embeddings except the given (session_id, node_id).
        """
        backend = self._get_backend_module()
        if not hasattr(backend, "get_all_lesson_embeddings_except_query"):
            raise NotImplementedError(
                "get_all_lesson_embeddings_except_query not implemented for this backend"
            )
        return backend.get_all_lesson_embeddings_except_query(session_id, node_id)

    def nearest_neighbors_query(self, target_embedding_json: str, top_k: int, user_id: int = None):
        """
        Find the k nearest neighbors to the target embedding using vector search.

        Args:
            target_embedding_json: JSON string representation of the target embedding
            top_k: Number of nearest neighbors to return

        Returns:
            List of rows with columns: session_id, node_id, distance
        """
        backend = self._get_backend_module()
        if not hasattr(backend, "nearest_neighbors_query"):
            raise NotImplementedError("nearest_neighbors_query not implemented for this backend")
        return backend.nearest_neighbors_query(target_embedding_json, top_k, user_id)

    def get_llm_call_input_api_type_query(self, session_id, node_id):
        """Get input and api_type from llm_calls by session_id and node_id."""
        backend = self._get_backend_module()
        return backend.get_llm_call_input_api_type_query(session_id, node_id)

    def get_llm_call_output_api_type_query(self, session_id, node_id):
        """Get output and api_type from llm_calls by session_id and node_id."""
        backend = self._get_backend_module()
        return backend.get_llm_call_output_api_type_query(session_id, node_id)

    def get_experiment_log_success_graph_query(self, session_id):
        """Get log, success, and graph_topology from experiments by session_id."""
        backend = self._get_backend_module()
        return backend.get_experiment_log_success_graph_query(session_id)

    def upsert_user_postgres_only(self, google_id, email, name, picture):
        """
        Upsert user only in PostgreSQL database.

        Users are only managed remotely via the auth service.
        SQLite is single-user and doesn't need user management.

        Args:
            google_id: Google OAuth ID
            email: User email
            name: User name
            picture: User profile picture URL

        Returns:
            User record from PostgreSQL
        """
        from aco.common.constants import REMOTE_DATABASE_URL

        if not REMOTE_DATABASE_URL:
            raise Exception("PostgreSQL not available - users can only be managed remotely")

        try:
            if self._postgres_module is None:
                from aco.server.database_backends import postgres

                self._postgres_module = postgres

            user_record = self._postgres_module.upsert_user(google_id, email, name, picture)
            logger.debug(f"User {email} upserted in PostgreSQL database")
            return user_record

        except Exception as e:
            logger.error(f"Failed to upsert user in PostgreSQL: {e}")
            raise

    def get_user_by_id_postgres_only(self, user_id):
        """
        Get user by their ID from PostgreSQL only.

        Args:
            user_id: The user's ID

        Returns:
            The user record or None if not found
        """
        from aco.common.constants import REMOTE_DATABASE_URL

        if not REMOTE_DATABASE_URL:
            raise Exception("PostgreSQL not available - users can only be queried remotely")

        try:
            if self._postgres_module is None:
                from aco.server.database_backends import postgres

                self._postgres_module = postgres

            return self._postgres_module.get_user_by_id_query(user_id)

        except Exception as e:
            logger.error(f"Failed to get user from PostgreSQL: {e}")
            raise


# Create singleton instance following the established pattern
DB = DatabaseManager()
