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
            self._postgres_module._shared_conn = None
            logger.debug("Cleared PostgreSQL connection cache")

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
        return backend.query_one(query, params)

    def query_all(self, query, params=None):
        """Execute query and return all rows."""
        backend = self._get_backend_module()
        return backend.query_all(query, params)

    def execute(self, query, params=None):
        """Execute query without returning results."""
        backend = self._get_backend_module()
        return backend.execute(query, params)

    def get_conn(self):
        """Get database connection."""
        backend = self._get_backend_module()
        return backend.get_conn()

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

    def add_experiment_to_db(self, session_id, parent_session_id, name, default_graph, timestamp, cwd, command, env_json, default_success, default_note, default_log):
        """Add experiment to database using backend-specific SQL syntax."""
        backend = self._get_backend_module()
        return backend.add_experiment_to_db(session_id, parent_session_id, name, default_graph, timestamp, cwd, command, env_json, default_success, default_note, default_log)


# Create singleton instance following the established pattern
DB = DatabaseManager()