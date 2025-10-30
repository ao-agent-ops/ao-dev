import os
from aco.common.config import Config
from aco.common.config import derive_project_root, generate_random_username


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


# Path to config.yaml.
default_config_path = os.path.join(ACO_HOME, "config.yaml")
ACO_CONFIG = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "ACO_CONFIG",
            default_config_path,
        )
    )
)

# Ensure config.yaml exists. Init with defaults if not present.
os.makedirs(os.path.dirname(ACO_CONFIG), exist_ok=True)
if not os.path.exists(ACO_CONFIG):
    default_config = Config(
        project_root=derive_project_root(),
        collect_telemetry=False,
        telemetry_url=None,
        telemetry_key=None,
        telemetry_username=generate_random_username(),
    )
    default_config.to_yaml_file(ACO_CONFIG)

# Load values from config file.
config = Config.from_yaml_file(ACO_CONFIG)

ACO_PROJECT_ROOT = config.project_root
COLLECT_TELEMETRY = config.collect_telemetry
TELEMETRY_URL = config.telemetry_url
TELEMETRY_KEY = config.telemetry_key
TELEMETRY_USERNAME = getattr(config, "telemetry_username", generate_random_username())

# server-related constants
HOST = "127.0.0.1"
PORT = 5959
CONNECTION_TIMEOUT = 5
SERVER_START_TIMEOUT = 2
PROCESS_TERMINATE_TIMEOUT = 5
MESSAGE_POLL_INTERVAL = 0.1
SERVER_START_WAIT = 1
SOCKET_TIMEOUT = 1
SHUTDOWN_WAIT = 2

# Experiment meta data.
DEFAULT_NOTE = "Take notes."
DEFAULT_LOG = "No entries"
DEFAULT_SUCCESS = ""
SUCCESS_STRING = {True: "Satisfactory", False: "Failed", None: ""}

# Colors
CERTAINTY_GREEN = "#00c542"
CERTAINTY_YELLOW = "#FFC000"
CERTAINTY_RED = "#B80F0A"
SUCCESS_COLORS = {
    "Satisfactory": CERTAINTY_GREEN,
    "": CERTAINTY_YELLOW,
    "Failed": CERTAINTY_RED,
}

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
os.makedirs(ACO_CACHE, exist_ok=True)


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
os.makedirs(ACO_DB_PATH, exist_ok=True)

# the path to the folder where the logs are stored
default_log_path = os.path.join(ACO_HOME, "logs")
log_dir = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "ACO_LOG_PATH",
            default_log_path,
        )
    )
)
os.makedirs(log_dir, exist_ok=True)
ACO_LOG_PATH = os.path.join(log_dir, "server.log")

default_attachment_cache = os.path.join(ACO_CACHE, "attachments")
ACO_ATTACHMENT_CACHE = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "ACO_ATTACHMENT_CACHE",
            default_attachment_cache,
        )
    )
)
os.makedirs(ACO_ATTACHMENT_CACHE, exist_ok=True)
