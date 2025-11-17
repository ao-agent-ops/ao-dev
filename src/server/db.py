from aco.common.logger import logger
from aco.common.constants import DATABASE_URL


# Check if we should use Postgres instead of SQLite
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    # Import and re-export all functions from postgres backend
    from aco.server.database_backends.postgres import (
        get_conn,
        query_one,
        query_all,
        execute,
        hash_input,
        deserialize_input,
        deserialize,
        store_taint_info,
        get_taint_info,
    )
    logger.info("Using PostgreSQL database backend")
else:
    # Import and re-export all functions from sqlite backend
    from aco.server.database_backends.sqlite import (
        get_conn,
        query_one,
        query_all,
        execute,
        hash_input,
        deserialize_input,
        deserialize,
        store_taint_info,
        get_taint_info,
    )
    logger.info("Using SQLite database backend")
