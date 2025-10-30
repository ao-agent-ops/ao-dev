import hashlib
import json
import os
import importlib
from pathlib import Path
import threading
from typing import Optional, Union


def is_valid_mod(mod_name: str):
    """Checks if one could import this module."""
    try:
        return importlib.util.find_spec(mod_name) is not None
    except:
        return False


def scan_user_py_files_and_modules(root_dir):
    """
    Scan a directory for all .py files and return:
      - user_py_files: set of absolute file paths
      - file_to_module: mapping from file path to module name (relative to root_dir)
    """
    user_py_files = set()
    file_to_module = dict()
    module_to_file = dict()
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                abs_path = os.path.abspath(os.path.join(dirpath, filename))
                user_py_files.add(abs_path)
                # Compute module name relative to root_dir
                rel_path = os.path.relpath(abs_path, root_dir)
                mod_name = rel_path[:-3].replace(os.sep, ".")  # strip .py, convert / to .
                if mod_name.endswith(".__init__"):
                    mod_name = mod_name[:-9]  # remove .__init__
                file_to_module[abs_path] = mod_name
                module_to_file[mod_name] = abs_path
                # is it possible to shorten the module name and still get a
                # valid import?
                mod_name = ".".join(mod_name.split(".")[1:])
                while is_valid_mod(mod_name):
                    # If it is, add it to the dict
                    module_to_file[mod_name] = abs_path
                    mod_name = ".".join(mod_name.split(".")[1:])

    return user_py_files, file_to_module, module_to_file


# ==============================================================================
# Communication with server.
# ==============================================================================

# Global lock for thread-safe server communication
_server_lock = threading.Lock()


def send_to_server(msg):
    """Thread-safe send message to server (no response expected)."""
    from aco.runner.context_manager import server_file

    if isinstance(msg, dict):
        msg = json.dumps(msg) + "\n"
    elif isinstance(msg, str) and msg[-1] != "\n":
        msg += "\n"
    with _server_lock:
        server_file.write(msg)
        server_file.flush()


def send_to_server_and_receive(msg):
    """Thread-safe send message to server and receive response."""
    from aco.runner.context_manager import server_file

    if isinstance(msg, dict):
        msg = json.dumps(msg) + "\n"
    elif isinstance(msg, str) and msg[-1] != "\n":
        msg += "\n"
    with _server_lock:
        server_file.write(msg)
        server_file.flush()
        response = json.loads(server_file.readline().strip())
        return response


def find_additional_packages_in_project_root(project_root: str):
    """
    Using the simple pyproject.toml and setup.py heuristic, determine
    whether there are additional packages that can be/are installed.
    """
    all_subdirectories = [Path(x[0]) for x in os.walk(project_root)]
    project_roots = list(
        set([os.fspath(sub_dir) for sub_dir in all_subdirectories if _has_package_markers(sub_dir)])
    )
    return project_roots


# ==============================================================================
# We try to derive the project root relative to the user working directory.
# All of the below is implementing this heuristic search.
# ==============================================================================
def derive_project_root(start: str | None = None) -> str:
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
        ".idea",  # JetBrains project
        ".vscode",  # VS Code project
    }
    return any((p / f).exists() for f in files) or any((p / d).is_dir() for d in dirs)


def _has_package_markers(p: Path) -> bool:
    """
    Things that strongly indicate "this is a project/repo root".
    You can extend this list to fit your org/monorepo conventions.
    """
    files = {
        "pyproject.toml",
        "setup.py",
    }
    return any((p / f).exists() for f in files)


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
        "library",  # macOS / shared
        "system",  # macOS
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


# ===============================================
# Helpers for writing attachments to disk.
# ===============================================
def stream_hash(stream):
    """Compute SHA-256 hash of a binary stream (reads full content into memory)."""
    content = stream.read()
    stream.seek(0)
    return hashlib.sha256(content).hexdigest()


def save_io_stream(stream, filename, dest_dir):
    """
    Save stream to dest_dir/filename. If filename already exists, find new unique one.
    """
    stream.seek(0)
    desired_path = os.path.join(dest_dir, filename)
    if not os.path.exists(desired_path):
        # No conflict, write directly
        with open(desired_path, "wb") as f:
            f.write(stream.read())
        stream.seek(0)
        return desired_path

    # Different content, find a unique name
    base, ext = os.path.splitext(filename)
    counter = 1
    while True:
        new_filename = f"{base}_{counter}{ext}"
        new_path = os.path.join(dest_dir, new_filename)
        if not os.path.exists(new_path):
            with open(new_path, "wb") as f:
                f.write(stream.read())
            stream.seek(0)
            return new_path

        counter += 1
