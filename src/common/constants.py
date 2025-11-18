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
        database_url=None,
    )
    default_config.to_yaml_file(ACO_CONFIG)






Different branches.

1. Commit (and push): On the left panel, add the changes you want to 
"commit" and then commit (put a message) and push (upload to github)
 --> Creating checkpoints. You can go back to them, and others can use your 
code (we usually coordinate this on discord)
 "can you merge mine into yours etc." "can you push something"

2. Branches: You work on X, I work on Y. It sucks if you need to use my 
unready code.
 --> Every feature / bug that we work on, we creat a branch. (create new branch: git checkout -b YOUR NAME)
 --> git branch: lists all branches you have locally.
 --> git checkout: jump onto a different branch: Maybe branch is not updated (newer version on github). Do git pull to update.

 --> Sync our code: I put your changes into mine or you put mine into yours
    - Go to the "receiver branch" where merges are applied: git merge APPLIED_CHANGES
      --> git merge main (on your branch). You branch is up to date with main (all updates on main are also on yours)
      --> git will apply all of Bob's changes to Alice's code base (a lot of times this is complementary)
      --> You change button color to be orange, I to green: CONFLICT

      You fixed issue X, I fixed issue Y (we both started from code base version A)
      --> We want to produce a code base version B, where both issues are fixed
--> merge branches: You take someone elses new features / bug fixes and APPLY to your code (aka. your branch)



2. Merge: Everyone has their 










# Load values from config file.
config = Config.from_yaml_file(ACO_CONFIG)

ACO_PROJECT_ROOT = config.project_root
COLLECT_TELEMETRY = config.collect_telemetry
TELEMETRY_URL = config.telemetry_url
TELEMETRY_KEY = config.telemetry_key
TELEMETRY_USERNAME = getattr(config, "telemetry_username", generate_random_username())

# NOTE: We decided to only support remote DB for now. This might change in the future
# and the code is there to also support SQLite. Only thing missing is that reruns need
# to know whether to look up data remote or local. IMO we should have separate 
# experiment lists.

# We're getting the env var here because the deployed web app can't access the config.
# DATABASE_URL = os.environ.get("DATABASE_URL") or config.database_url
DATABASE_URL = "postgresql://postgres:WorkflowAurora2024@workflow-postgres.cm14iy6021bi.us-east-1.rds.amazonaws.com:5432/workflow_db"

# server-related constants
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PYTHON_PORT", 5959))
CONNECTION_TIMEOUT = 5
SERVER_START_TIMEOUT = 2
PROCESS_TERMINATE_TIMEOUT = 5
MESSAGE_POLL_INTERVAL = 0.1
FILE_POLL_INTERVAL = 1  # Interval in seconds for polling file changes for AST recompilation
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

# Path to the agent-copilot installation directory
# Computed from this file's location: aco/common/constants.py -> agent-copilot/
ACO_INSTALL_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
