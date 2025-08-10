import os
from common.utils import derive_project_root

# server-related constants
HOST = "127.0.0.1"
PORT = 5959
SOCKET_TIMEOUT = 1
SHUTDOWN_WAIT = 2


# default home directory for configs and temporary/cached files
default_home: str = os.path.join(os.path.expanduser("~"), ".cache")
ACO_HOME: str = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "ACO_HOME",
            os.path.join(os.getenv("XDG_CACHE_HOME", default_home), "agent-copilot"),
        )
    )
)
os.makedirs(ACO_HOME, exist_ok=True)


# Path to config.yaml. This config file includes the possible
# command line args. Must be generated with `aco config`.
# > Note: This does not need to be set. You can also just pass
# the relevant command line args when you run `aco-launch`.
default_config_path = os.path.join(ACO_HOME, "config.yaml")
ACO_CONFIG = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "ACO_CONFIG",
            default_config_path,
        )
    )
)
os.makedirs(os.path.dirname(ACO_CONFIG), exist_ok=True)


# Anything cache-related should be stored here
default_cache_path = os.path.join(ACO_HOME, "cache")
ACO_CACHE = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "ACO_CACHE",
            default_cache_path,
        )
    )
)
os.makedirs(os.path.dirname(ACO_CACHE), exist_ok=True)


# the path to the folder where the experiments database is
# stored
default_db_cache_path = os.path.join(ACO_HOME, "db")
ACO_DB_PATH = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "ACO_DB_PATH",
            default_db_cache_path,
        )
    )
)
os.makedirs(os.path.dirname(ACO_DB_PATH), exist_ok=True)


default_attachment_cache = os.path.join(ACO_CACHE, "attachments")
ACO_ATTACHMENT_CACHE = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "ACO_ATTACHMENT_CACHE",
            default_attachment_cache,
        )
    )
)
os.makedirs(os.path.dirname(ACO_ATTACHMENT_CACHE), exist_ok=True)


# project root is only inferred once at import-time
# here, we derive it based on heuristics.
# User can also pass project_root like this:
# aco-launch --project-root <ro/root> script.py
# In this case, the derived project root is overwritten
ACO_PROJECT_ROOT = derive_project_root()
