import os
import inspect
import yaml


def rel_path_to_abs(abs_file_path, rel_to_file):
    """
    Use __file__ as first argumante (abs_fil_path).
    Then use "agent-copilot/foo/bar.json" if your path is relative to the repo root.
    or just whatever if it's relative to the file (e.g., "../foo/bar.json")
    """
    # Normalize rel_to_file
    rel_to_file = os.path.normpath(rel_to_file)

    if rel_to_file.startswith("agent-copilot" + os.sep) or rel_to_file == "agent-copilot":
        # Assume project root is one of the parent directories containing "agent-copilot"
        current = abs_file_path
        while True:
            current = os.path.dirname(current)
            if os.path.basename(current) == "agent-copilot":
                project_root = current
                break
            if current == os.path.dirname(current):  # Reached filesystem root
                raise ValueError("Could not find 'agent-copilot' project root.")
        return os.path.abspath(os.path.join(project_root, os.path.relpath(rel_to_file, "agent-copilot")))
    else:
        # Treat as relative to the current file's directory
        return os.path.abspath(os.path.join(os.path.dirname(abs_file_path), rel_to_file))


def extract_key_args(fn, args, kwargs, key_names):
    """
    Robustly extract key arguments (by name) from a function call, handling positional, keyword, and default values.
    Returns a tuple of values for the requested key_names.
    """
    sig = inspect.signature(fn)
    try:
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
    except Exception as e:
        # Fallback: try to get from kwargs only
        return tuple(kwargs.get(k) for k in key_names)
    return tuple(bound.arguments.get(k) for k in key_names)


def ensure_project_root_in_copilot_yaml(config_path, default_root=None):
    """
    Ensure that copilot.yaml has a project_root entry. If not, set it using default_root or dynamic logic.
    Returns the project_root path.
    Throws a clear error if project root cannot be determined.
    """
    # Load YAML config
    if not os.path.exists(config_path):
        config = {}
    else:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}

    if 'project_root' in config and config['project_root']:
        return config['project_root']

    # Compute default if not provided
    if default_root is None:
        # Dynamic logic: look for pyproject.toml, .git
        current = os.getcwd()
        found = False
        while current != os.path.dirname(current):
            if (os.path.exists(os.path.join(current, 'pyproject.toml')) or
                os.path.exists(os.path.join(current, '.git'))):
                default_root = current
                found = True
                break
            current = os.path.dirname(current)
        if not found:
            raise RuntimeError(
                "Could not determine project root. Please create a pyproject.toml or .git in your project root, "
                "or set 'project_root' manually in configs/copilot.yaml."
            )

    config['project_root'] = default_root
    # Write back to YAML
    with open(config_path, 'w') as f:
        yaml.safe_dump(config, f)
    return default_root


def scan_user_py_files_and_modules(root_dir):
    """
    Scan a directory for all .py files and return:
      - user_py_files: set of absolute file paths
      - file_to_module: mapping from file path to module name (relative to root_dir)
    """
    user_py_files = set()
    file_to_module = dict()
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith('.py'):
                abs_path = os.path.abspath(os.path.join(dirpath, filename))
                user_py_files.add(abs_path)
                # Compute module name relative to root_dir
                rel_path = os.path.relpath(abs_path, root_dir)
                mod_name = rel_path[:-3].replace(os.sep, '.')  # strip .py, convert / to .
                if mod_name.endswith(".__init__"):
                    mod_name = mod_name[:-9]  # remove .__init__
                file_to_module[abs_path] = mod_name
    return user_py_files, file_to_module


def get_config_path():
    """Return the absolute path to configs/copilot.yaml."""
    import os
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'configs', 'copilot.yaml'))

def get_project_root():
    """Return the project root as set in copilot.yaml (ensuring it is set)."""
    config_path = get_config_path()
    return ensure_project_root_in_copilot_yaml(config_path)
