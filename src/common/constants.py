import re
import os
from ao.common.config import Config, derive_project_root


# default home directory for configs and temporary/cached files
default_home: str = os.path.join(os.path.expanduser("~"), ".cache")
AO_HOME: str = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "AO_HOME",
            os.path.join(os.getenv("XDG_CACHE_HOME", default_home), "ao"),
        )
    )
)
os.makedirs(AO_HOME, exist_ok=True)


# Path to config.yaml.
default_config_path = os.path.join(AO_HOME, "config.yaml")
AO_CONFIG = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "AO_CONFIG",
            default_config_path,
        )
    )
)

# Ensure config.yaml exists. Init with defaults if not present.
os.makedirs(os.path.dirname(AO_CONFIG), exist_ok=True)
if not os.path.exists(AO_CONFIG):
    default_config = Config(
        project_root=derive_project_root(),
        database_url=None,
    )
    default_config.to_yaml_file(AO_CONFIG)

# Load values from config file.
config = Config.from_yaml_file(AO_CONFIG)

AO_PROJECT_ROOT = config.project_root

# Remote PostgreSQL database URL for "Remote" mode in UI dropdown
REMOTE_DATABASE_URL = os.environ.get("DB_URL", "Unavailable")

# server-related constants
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PYTHON_PORT", 5959))
CONNECTION_TIMEOUT = 5
SERVER_START_TIMEOUT = 2
PROCESS_TERMINATE_TIMEOUT = 5
MESSAGE_POLL_INTERVAL = 0.1
FILE_POLL_INTERVAL = 1  # Interval in seconds for polling file changes for AST recompilation
ORPHAN_POLL_INTERVAL = 60  # Interval in seconds for checking if parent process died
SERVER_INACTIVITY_TIMEOUT = 1200  # Shutdown server after 20 min of inactivity
SERVER_START_WAIT = 1
SOCKET_TIMEOUT = 1
SHUTDOWN_WAIT = 2

# Experiment meta data.
DEFAULT_NOTE = "Take notes."
DEFAULT_LOG = "No entries"
DEFAULT_SUCCESS = ""
SUCCESS_STRING = {True: "Satisfactory", False: "Failed", None: ""}


# Node label constants
MAX_LABEL_LENGTH = 20
NO_LABEL = "No Label"

CERTAINTY_UNKNOWN = "#000000"
CERTAINTY_GREEN = "#7fc17b"  # Matches restart/rerun button
CERTAINTY_YELLOW = "#d4a825"  # Matches tag icon; currently unused
CERTAINTY_RED = "#e05252"  # Matches erase button
SUCCESS_COLORS = {
    "Satisfactory": CERTAINTY_GREEN,
    "": CERTAINTY_UNKNOWN,
    "Failed": CERTAINTY_RED,
}

# Anything cache-related should be stored here
default_cache_path = os.path.join(AO_HOME, "cache")
AO_CACHE = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "AO_CACHE",
            default_cache_path,
        )
    )
)
os.makedirs(AO_CACHE, exist_ok=True)

# Centralized cache for AST-rewritten .pyc files
# All compiled user code goes here (hidden from user, no cleanup needed)
AO_CACHE_DIR = os.path.join(AO_HOME, "pyc")
os.makedirs(AO_CACHE_DIR, exist_ok=True)

# Git repository for code versioning (separate from user's git)
default_git_path = os.path.join(AO_HOME, "git")
GIT_DIR = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "GIT_DIR",
            default_git_path,
        )
    )
)
# Note: Don't create the directory here - let GitVersioner handle initialization


# the path to the folder where the experiments database is stored
default_db_cache_path = os.path.join(AO_HOME, "db")
DB_PATH = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "DB_PATH",
            default_db_cache_path,
        )
    )
)
os.makedirs(DB_PATH, exist_ok=True)

# the path to the folder where the logs are stored
default_log_path = os.path.join(AO_HOME, "logs")
AO_LOG_DIR = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "AO_LOG_DIR",
            default_log_path,
        )
    )
)
os.makedirs(AO_LOG_DIR, exist_ok=True)
MAIN_SERVER_LOG = os.path.join(AO_LOG_DIR, "main_server.log")
FILE_WATCHER_LOG = os.path.join(AO_LOG_DIR, "file_watcher.log")
GIT_VERSIONER_LOG = os.path.join(AO_LOG_DIR, "git_versioner.log")

default_attachment_cache = os.path.join(AO_CACHE, "attachments")
ATTACHMENT_CACHE = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "ATTACHMENT_CACHE",
            default_attachment_cache,
        )
    )
)
os.makedirs(ATTACHMENT_CACHE, exist_ok=True)

# Path to the ao package directory
# Computed from this file's location: ao/common/constants.py -> ao/
# Works for both editable installs (src/) and pip installs (site-packages/ao/)
AO_INSTALL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Whitelist patterns as (url_regex, path_regex) tuples.
# A request matches if BOTH regexes match (use ".*" for "any").
# Note: path may include query params (e.g., /search?q=...), so don't use $ anchor.
WHITELIST_ENDPOINT_PATTERNS = [
    # LLM APIs (any URL, match by path)
    (r".*", r"/v1/messages"),  # Anthropic
    (r".*", r"/v1/responses"),  # OpenAI
    (r".*", r"/v1/chat/completions"),  # OpenAI
    (r".*", r"models/[^/]+:generateContent"),  # Google GenAI
    (r".*", r"models/[^/]+:streamGenerateContent"),  # Google GenAI
    (r".*", r"/api/chat"),  # Ollama
    (r".*", r"/api/generate"),  # Ollama
    (r".*", r"/api/embed"),  # Ollama embeddings (single)
    (r".*", r"/api/embeddings"),  # Ollama embeddings (batch)
    # CrewAI Tool APIs
    (r"serper\.dev", r".*"),  # All Serper tools (search, scrape, etc.)
    (r".*api\.search\.brave\.com", r"/res/v1/web/search"),  # BraveSearchTool
    (r".*r\.jina\.ai", r".*"),  # JinaScrapeWebsiteTool (any path, URL contains target)
    (r".*api\.brightdata\.com", r"/request"),  # BrightDataSerpTool, BrightDataUnlockerTool
    (r".*api\.patronus\.ai", r"/v1/evaluate"),  # PatronusEvalTool
    (r".*api\.contextual\.ai", r"/v1/datastores/"),  # ContextualAI query
    (r".*api\.contextual\.ai", r"/v1/parse"),  # ContextualAI parse
    (r".*api\.contextual\.ai", r"/v1/rerank"),  # ContextualAI rerank
    (r".*api\.parallel\.ai", r"/v1beta/search"),  # ParallelSearchTool
]
COMPILED_ENDPOINT_PATTERNS = [
    (re.compile(url_pat), re.compile(path_pat))
    for url_pat, path_pat in WHITELIST_ENDPOINT_PATTERNS
]

# List of regexes that exclude patterns from being displayed in edit IO
EDIT_IO_EXCLUDE_PATTERNS = [
    r"^_.*",
    # Top-level fields
    r"^max_tokens$",
    r"^stream$",
    r"^temperature$",
    # content.* fields (metadata, usage, system info)
    r"^content\.id$",
    r"^content\.type$",
    r"^content\.object$",
    r"^content\.created(_at)?$",
    r"^content\.completed_at$",
    r"^content\.model$",
    r"^content\.status$",
    r"^content\.background$",
    r"^content\.metadata",
    r"^content\.usage",
    r"^content\.service_tier$",
    r"^content\.system_fingerprint$",
    r"^content\.stop_reason$",
    r"^content\.stop_sequence$",
    r"^content\.billing",
    r"^content\.error$",
    r"^content\.incomplete_details$",
    r"^content\.max_output_tokens$",
    r"^content\.max_tool_calls$",
    r"^content\.parallel_tool_calls$",
    r"^content\.previous_response_id$",
    r"^content\.prompt_cache",
    r"^content\.reasoning\.(effort|summary)$",
    r"^content\.safety_identifier$",
    r"^content\.store$",
    r"^content\.temperature$",
    r"^content\.text\.(format\.type|verbosity)$",
    r"^content\.tool_choice$",
    r"^content\.top_(logprobs|p)$",
    r"^content\.truncation$",
    r"^content\.user$",
    r"^content\.responseId$",
    # content.content.* fields (array elements)
    r"^content\.content\.\d+\.(type|id)$",
    r"^content\.content\.\d+\.content\.\d+\.type$",
    # content.choices.* fields
    r"^content\.choices\.\d+\.index$",
    r"^content\.choices\.\d+\.message\.(refusal|annotations|reasoning)$",
    r"^content\.choices\.\d+\.(finish_reason|logprobs|seed)$",
    # content.output.* fields
    r"^content\.output\.\d+\.(id|type|status)$",
    r"^content\.output\.\d+\.content\.\d+\.(type|annotations|logprobs)$",
    # content.candidates.* fields (Google Gemini)
    r"^content\.candidates\.\d+\.(finishReason|index)$",
    r"^content\.usageMetadata",
    # tools.* fields
    r"^tools\.\d+\.parameters\.(additionalProperties|properties|required|type)$",
    r"^tools\.\d+\.strict$",
    # Ollama response fields (timing/stats)
    r"^content\.done$",
    r"^content\.done_reason$",
    r"^content\.eval_count$",
    r"^content\.eval_duration$",
    r"^content\.load_duration$",
    r"^content\.prompt_eval_count$",
    r"^content\.prompt_eval_duration$",
    r"^content\.total_duration$",
]

# Regex patterns to look up display names for nodes in the graph
# Each key is a regex pattern that matches URLs, value is the display name
URL_PATTERN_TO_NODE_NAME = [
    # Serper tools (different subdomains for different tools)
    (r"google\.serper\.dev", "Serper Search"),
    (r"scrape\.serper\.dev", "Serper Scrape"),
    # Brave Search
    (r"api\.search\.brave\.com/res/v1/web/search", "Brave Search"),
    # Jina (URL contains target site in path)
    (r"r\.jina\.ai/", "Jina Scrape"),
    # BrightData
    (r"api\.brightdata\.com/request", "BrightData"),
    # Patronus
    (r"api\.patronus\.ai/v1/evaluate", "Patronus Eval"),
    # ContextualAI
    (r"api\.contextual\.ai/v1/parse", "Contextual Parse"),
    (r"api\.contextual\.ai/v1/rerank", "Contextual Rerank"),
    # Parallel AI
    (r"api\.parallel\.ai/v1beta/search", "Parallel Search"),
]
COMPILED_URL_PATTERN_TO_NODE_NAME = [
    (re.compile(pattern), name) for pattern, name in URL_PATTERN_TO_NODE_NAME
]

# Exact match patterns for known models -> clean display names
# These are matched against the raw model name before cleanup rules are applied
MODEL_NAME_PATTERNS = [
    # OpenAI
    (r"^gpt-4o-mini$", "GPT-4o Mini"),
    (r"^gpt-4o$", "GPT-4o"),
    (r"^gpt-4-turbo$", "GPT-4 Turbo"),
    (r"^gpt-4$", "GPT-4"),
    (r"^gpt-3\.5-turbo$", "GPT-3.5 Turbo"),
    (r"^o1-preview$", "O1 Preview"),
    (r"^o1-mini$", "O1 Mini"),
    # Anthropic
    (r"^claude-sonnet-4-5", "Claude Sonnet 4.5"),
    (r"^claude-3-5-sonnet", "Claude 3.5 Sonnet"),
    (r"^claude-3-5-haiku", "Claude 3.5 Haiku"),
    (r"^claude-3-opus", "Claude 3 Opus"),
    # Google
    (r"^gemini-2\.0-flash", "Gemini 2.0 Flash"),
    (r"^gemini-2\.5-flash", "Gemini 2.5 Flash"),
    (r"^gemini-1\.5-pro", "Gemini 1.5 Pro"),
    (r"^gemini-1\.5-flash", "Gemini 1.5 Flash"),
]
COMPILED_MODEL_NAME_PATTERNS = [
    (re.compile(pattern), name) for pattern, name in MODEL_NAME_PATTERNS
]

INVALID_LABEL_CHARS = set("{[<>%$#@")