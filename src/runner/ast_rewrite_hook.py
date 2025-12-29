import os
import sys
from importlib.abc import MetaPathFinder, SourceLoader
from importlib.util import spec_from_loader
import marshal
from ao.common.logger import logger
from ao.server.file_watcher import rewrite_source_to_code, get_pyc_path
from ao.common.utils import should_rewrite


_module_to_user_file = dict()
_notified_files = set()  # Track files we've already notified FileWatcher about
_skip_modules = set()  # Cache of modules we've determined shouldn't be rewritten


def set_module_to_user_file(module_to_user_file: dict):
    global _module_to_user_file
    _module_to_user_file = module_to_user_file


def _find_module_file(fullname: str, path) -> str | None:
    """
    Find the source file for a module without importing it.

    Args:
        fullname: Fully qualified module name (e.g., 'mypackage.mymodule')
        path: Search path (from find_spec)

    Returns:
        Absolute path to the .py file, or None if not found
    """
    parts = fullname.split(".")
    module_file = parts[-1] + ".py"
    package_init = os.path.join(*parts, "__init__.py") if len(parts) > 1 else None

    # Search in provided path first, then sys.path
    search_paths = []
    if path:
        search_paths.extend(path)
    search_paths.extend(sys.path)

    for base in search_paths:
        if not base or not os.path.isdir(base):
            continue

        # Try as a module file
        candidate = (
            os.path.join(base, *parts[:-1], module_file)
            if len(parts) > 1
            else os.path.join(base, module_file)
        )
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

        # Try as a package (__init__.py)
        if package_init:
            candidate = os.path.join(base, package_init)
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

        # Try as a single-level package
        candidate = os.path.join(base, *parts, "__init__.py")
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

    return None


def _notify_file_watcher(file_path: str) -> None:
    """
    Notify FileWatcher about a newly discovered file to monitor.

    Sends a 'watch_file' message to the server, which forwards it to FileWatcher.
    Only notifies once per file per session.
    """
    global _notified_files
    if file_path in _notified_files:
        return
    _notified_files.add(file_path)

    try:
        from ao.common.utils import send_to_server

        send_to_server({"type": "watch_file", "path": file_path})
    except Exception as e:
        # Don't fail the import if notification fails
        logger.debug(f"[ASTHook] Failed to notify FileWatcher about {file_path}: {e}")


class ASTImportLoader(SourceLoader):
    def __init__(self, fullname, path):
        self.fullname = fullname
        self.path = path

    def get_filename(self, fullname):
        return self.path

    def get_data(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def source_to_code(self, data, path, *, _optimize=-1):
        """
        Load code from cache if fresh, otherwise compile and notify FileWatcher.

        With centralized cache in ~/.cache/ao/pyc/, all .pyc files are ours,
        so we only need to check freshness (source mtime vs pyc mtime).
        """
        # Skip .pyc loading for __init__.py - file_watcher doesn't compile them
        # to avoid circular import issues from injected taint imports
        if os.path.basename(path) == "__init__.py":
            return rewrite_source_to_code(data, path, module_to_file=_module_to_user_file)

        # Try to load from cache
        try:
            pyc_path = get_pyc_path(path)
            # Check freshness: pyc newer than source means cache is valid
            if os.path.getmtime(pyc_path) > os.path.getmtime(path):
                with open(pyc_path, "rb") as f:
                    f.read(16)  # skip header
                    return marshal.load(f)
        except OSError:
            pass  # Cache miss - compile below

        # Cache miss - compile on demand
        code_object = rewrite_source_to_code(data, path, module_to_file=_module_to_user_file)

        # Notify FileWatcher about this file (if not already notified)
        _notify_file_watcher(path)

        return code_object


class ASTImportFinder(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        """
        Find and return a module spec for modules that should be AST-rewritten.

        Uses O(1) dict lookup for known modules, then falls back to blacklist
        heuristic for unknown modules.
        """
        # Fast path: skip modules we've already determined shouldn't be rewritten
        if fullname in _skip_modules:
            return None

        # O(1) lookup for known user modules
        if fullname in _module_to_user_file:
            return spec_from_loader(
                fullname, ASTImportLoader(fullname, _module_to_user_file[fullname])
            )

        # Fast path: if parent module is skipped, skip submodules too
        if "." in fullname:
            parent = fullname.rsplit(".", 1)[0]
            if parent in _skip_modules:
                _skip_modules.add(fullname)
                return None

        # For unknown modules, check if they should be rewritten using blacklist heuristic
        # This handles dynamically discovered files (e.g., from other sys.path entries)
        file_path = _find_module_file(fullname, path)
        if file_path and should_rewrite(file_path):
            # Add to our tracking dict for future lookups
            _module_to_user_file[fullname] = file_path
            return spec_from_loader(fullname, ASTImportLoader(fullname, file_path))

        # Cache this module as one we shouldn't rewrite
        _skip_modules.add(fullname)
        return None


def install_patch_hook():
    """
    Install the AST rewrite import hook.

    This hook intercepts imports of modules in _module_to_user_file and
    applies AST transformations before they are loaded.
    """
    # put the AST re-write first to make sure we re-write the user-defined in
    # files/modules
    if not any(isinstance(f, ASTImportFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, ASTImportFinder())
