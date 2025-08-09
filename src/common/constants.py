import os


# server-related constants
HOST = '127.0.0.1'
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


# Path to config.yaml. This config file includes the possible
# command line args. Must be generated with `aco config`.
# > Note: This does not need to be set. You can also just pass
# the relevant command line args when you run `aco develop`.
default_config_path = os.path.join(ACO_HOME, "config.yaml")
ACO_CONFIG = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "ACO_CONFIG",
            default_config_path,
        )
    )
)


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


# project root
def safe_infer_project_root() -> str:
    """
    Infer the project root directory by finding the directory that contains
    the 'src' subdirectory with the 'agent_copilot' folder.
    
    Returns:
        str: The absolute path to the project root directory
        
    Raises:
        RuntimeError: If the project root cannot be determined
    """
    # Start from the current file's directory (src/common/constants.py)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Go up directories until we find the project root
    # The project root should contain 'src' with both 'common' and 'agent_copilot'
    search_dir = current_dir

    # init project root
    project_root = None
    
    while True:
        # Check if this directory contains src with the expected subdirectories
        src_path = os.path.join(search_dir, 'src')
        if (os.path.isdir(src_path) and 
            os.path.isdir(os.path.join(src_path, 'agent_copilot'))):
            project_root = search_dir
            break
        
        # Move up one level
        parent_dir = os.path.dirname(search_dir)
        
        # Stop if we've reached the filesystem root
        if parent_dir == search_dir:
            break
            
        search_dir = parent_dir
    
    if project_root is None:
        raise RuntimeError(
            f"Could not infer project root. Started from {current_dir} "
            f"and searched up to filesystem root without finding a directory "
            f"containing 'src' with both 'common' and 'agent_copilot' subdirectories."
        )
    else:
        assert os.path.isdir(project_root) and os.path.isdir(os.path.join(project_root, 'src/agent_copilot')), \
            "project root found but incorrect."
        return project_root


ACO_PROJECT_ROOT = safe_infer_project_root()