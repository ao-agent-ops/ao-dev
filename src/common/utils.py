from __future__ import annotations
import os
from pathlib import Path
from typing import Optional, Union

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
    # TODO: Is this still needed? Only used in cache manager.
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'configs', 'copilot.yaml'))

def get_project_root() -> str:
    """Return the project root as set in copilot.yaml (ensuring it is set)."""
    # TODO: Check if the project root is stored in config.
    # TODO: If not: return derive_project_root()
    # TODO: Delete below.
    config_path = get_config_path()
    return ensure_project_root_in_copilot_yaml(config_path)

# TODO: delete this function (used in develop.py).
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

# ==============================================================================
# We try to derive the project root relative to the user working directory. 
# All of the below is implementing this heuristic search.
# ==============================================================================
def derive_project_root() -> str:
    """
    Walk upward from current working directory to infer a Python project root.

    Heuristics (in order of strength):
      1) If the directory contains project/repo markers (pyproject.toml, .git, etc.), STOP and return it.
      2) If a parent directory name cannot be part of a Python module path (not an identifier), STOP at that directory.
      3) If we encounter common non-project anchor dirs (~/Documents, ~/Downloads, /usr, C:\\Windows, /Applications, etc.),
         DO NOT go above them; return the last "good" directory below.
      4) If we detect we're about to cross a virtualenv boundary, return the last good directory below.
      5) If we hit the filesystem root without any better signal, return the last good directory we saw.

    "Last good directory" = the most recent directory we visited that could plausibly be part of an importable path
    (i.e., its name is a valid identifier or it's a top-level candidate that doesn't obviously look like an anchor).

    Returns:
        String path to the inferred project root.
    """
    start = os.getcwd()
    cur = _normalize_start(start)
    last_good = cur

    for p in _walk_up(cur):
        # Strong signal: repo/project markers at this directory
        if _has_project_markers(p) or _has_src_layout_hint(p):
            return str(p)

        # If this segment cannot be in a Python dotted path, don't go above it.
        if not _segment_is_import_safe(p):
            return str(p)

        # If this is a known "anchor" (Documents, Downloads, Program Files, /usr, etc.),
        # don't float above it; the project likely lives below.
        if _is_common_non_project_dir(p):
            return str(last_good)

        # Don't float above a virtualenv boundary (if start happened to be inside one).
        if _looks_like_virtualenv_root(p):
            return str(last_good)

        # If nothing special, this remains a reasonable candidate.
        last_good = p

    # We reached the OS root without a decisive marker.
    return str(last_good)

def _normalize_start(start: Optional[Union[str, os.PathLike]]) -> Path:
    if start is None:
        start = Path.cwd()
    p = Path(start)
    if p.is_file():
        p = p.parent
    return p.resolve()


def _walk_up(start_dir: Path):
    """Yield start_dir, then its parents up to the filesystem root."""
    p = start_dir
    while True:
        yield p
        if p.parent == p:
            break  # reached filesystem root
        p = p.parent


def _has_project_markers(p: Path) -> bool:
    """
    Things that strongly indicate "this is a project/repo root".
    You can extend this list to fit your org/monorepo conventions.
    """
    files = {
        "pyproject.toml",
        "poetry.lock",
        "Pipfile",
        "requirements.txt",
        "setup.cfg",
        "setup.py",
        "tox.ini",
        ".editorconfig",
        ".flake8",
        "mypy.ini",
        "README.md",
        "README.rst",
    }
    dirs = {
        ".git",
        ".hg",
        ".svn",
        ".idea",      # JetBrains project
        ".vscode",    # VS Code project
    }
    return any((p / f).exists() for f in files) or any((p / d).is_dir() for d in dirs)


def _has_src_layout_hint(p: Path) -> bool:
    """
    Mild positive signal: a 'src/' directory that appears to contain importable packages.
    We don't require __init__.py (PEP 420 namespaces exist). We only treat this as a hint,
    not as strong as explicit markers—so it's folded into `_has_project_markers`-like logic.
    """
    src = p / "src"
    if not src.is_dir():
        return False

    # Does src contain at least one directory that looks like a Python package segment?
    for child in src.iterdir():
        if child.is_dir() and _name_looks_like_package(child.name):
            return True
    return False


def _segment_is_import_safe(p: Path) -> bool:
    """
    A directory name that cannot be a valid Python identifier cannot be part of a dotted module path.
    If it's not import-safe, we don't go above it (we stop at it).
    """
    name = p.name
    # At filesystem root, name may be '' (POSIX) or 'C:\\' (Windows); treat as non-import-segment.
    if name == "" or p.parent == p:
        return False
    return name.isidentifier()


def _name_looks_like_package(name: str) -> bool:
    """
    Heuristic for a directory that *could* be an importable package:
    - valid identifier (letters, digits, underscore; not starting with digit)
    """
    return name.isidentifier()


def _looks_like_virtualenv_root(p: Path) -> bool:
    """
    Common virtualenv layouts:
      - <venv>/bin/activate      (POSIX)
      - <venv>/Scripts/activate  (Windows)
    Also many people name the dir 'venv', '.venv', 'env', '.env'
    """
    if p.name in {"venv", ".venv", "env", ".env"}:
        return True
    if (p / "bin" / "activate").is_file():
        return True
    if (p / "Scripts" / "activate").is_file():
        return True
    return False


def _is_common_non_project_dir(p: Path) -> bool:
    """
    Directories that are very often "anchors" above real projects.
    We avoid floating above these; instead we return the last good dir below them.
    This is conservative and OS-aware.
    """
    # Normalize case on Windows to avoid case-sensitivity surprises.
    name_lower = p.name.lower()

    home = Path.home()
    try:
        in_home = home in p.parents or p == home
    except Exception:
        in_home = False

    # --- macOS / Linux-ish anchors ---
    posix_anchors = {
        "applications",  # macOS
        "library",       # macOS / shared
        "system",        # macOS
        "usr",
        "bin",
        "sbin",
        "etc",
        "var",
        "opt",
        "proc",
        "dev",
    }
    posix_home_anchors = {
        "documents",
        "downloads",
        "desktop",
        "music",
        "movies",
        "pictures",
        "public",
        "library",  # user's Library on macOS
    }

    # --- Windows anchors ---
    windows_anchors = {
        "windows",
        "program files",
        "program files (x86)",
        "programdata",
        "intel",
        "nvidia corporation",
    }
    windows_home_anchors = {
        "documents",
        "downloads",
        "desktop",
        "pictures",
        "music",
        "videos",
        "onedrive",
        "dropbox",
    }

    # Filesystem root? Treat as an anchor we don't climb past.
    if p.parent == p:
        return True

    if os.name == "nt":
        if name_lower in windows_anchors:
            return True
        if in_home and name_lower in windows_home_anchors:
            return True
        # Example: C:\Users\<me>\Documents — stop at Documents
        if in_home and name_lower == "users":
            return True
    else:
        if name_lower in posix_anchors:
            return True
        if in_home and name_lower in posix_home_anchors:
            return True

    # Generic cloud-sync / archive / tooling anchors (cross-platform):
    generic_anchors = {
        "icloud drive",
        "google drive",
        "dropbox",
        "box",
        "library",  # often a user-level anchor on macOS
        "applications",  # second chance
    }
    if name_lower in generic_anchors:
        return True

    return False

