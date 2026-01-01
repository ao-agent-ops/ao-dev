"""
File watcher process for precompiling AST-rewritten .pyc files.

This module implements a background process that monitors user code files
for changes and automatically recompiles them with AST rewrites to .pyc files.
This eliminates the startup overhead of AST transformation by using Python's
native .pyc loading mechanism.

Key Features:
- Polls user module files for changes based on modification time
- Precompiles changed files with taint propagation AST rewrites
- Writes .pyc files to standard __pycache__ location for Python to discover
- Runs as a separate process spawned by the develop server
"""

import ast
import os
import sys
import time
import signal
import glob
import hashlib
import hashlib
import threading
import queue
import subprocess
import shutil
import traceback
from datetime import datetime
from typing import Dict, Set, Optional
from ao.common.logger import create_file_logger
from ao.common.constants import (
    FILE_POLL_INTERVAL,
    ORPHAN_POLL_INTERVAL,
    AO_PROJECT_ROOT,
    AO_CACHE_DIR,
    FILE_WATCHER_LOG,
    GIT_DIR,
)

logger = create_file_logger(FILE_WATCHER_LOG)
from ao.server.ast_transformer import TaintPropagationTransformer


def rewrite_source_to_code(source: str, filename: str, user_files: set = None, return_tree=False):
    """
    Transform and compile Python source code with AST rewrites.

    Args:
        source: Python source code as a string
        filename: Path to the source file (used in error messages and code object)
        user_files: Set of user code file paths (to distinguish from third-party code)
        return_tree: If True, return (code_object, tree) tuple for debugging

    Returns:
        A compiled code object ready for execution, or (code_object, tree) if return_tree=True
    """
    # Inject future imports to prevent type annotations from being evaluated at import time
    if "from __future__ import annotations" not in source:
        source = "from __future__ import annotations\n" + source

    tree = ast.parse(source, filename=filename)

    transformer = TaintPropagationTransformer(user_files=user_files, current_file=filename)
    tree = transformer.visit(tree)
    tree = transformer._inject_taint_imports(tree)
    ast.fix_missing_locations(tree)

    code_object = compile(tree, filename, "exec")

    if return_tree:
        return code_object, tree
    return code_object


class FileWatcher:
    """
    Monitors user module files and precompiles them with AST rewrites.

    This class tracks modification times of user modules and automatically
    recompiles them to .pyc files when changes are detected. The compiled
    .pyc files contain the AST-rewritten code with taint propagation.
    """

    def __init__(self, project_root: str = None, watch_queue=None, response_queue=None):
        """
        Initialize the file watcher.

        Args:
            project_root: Root directory to scan for Python files.
                         Falls back to AO_PROJECT_ROOT if not provided.
            watch_queue: multiprocessing.Queue for receiving messages from MainServer.
            response_queue: multiprocessing.Queue for sending messages back to MainServer.
        """
        self.tracked_files: Set[str] = set()
        self.file_mtimes: Dict[str, float] = {}
        self.pid = os.getpid()
        self._parent_pid = os.getppid()
        self._shutdown = False
        self.project_root = project_root or AO_PROJECT_ROOT
        self.watch_queue = watch_queue
        self.response_queue = response_queue
        # Git versioning state (lazy init)
        self._git_available: Optional[bool] = None
        self._git_initialized = False
        self._git_dir = os.path.abspath(GIT_DIR)
        logger.info(f"Started with project_root: {self.project_root}")
        self._setup_signal_handlers()

    # =========================================================================
    # Git Versioning (moved from git_versioner.py)
    # =========================================================================

    def _is_git_available(self) -> bool:
        """Check if git is installed on the system."""
        if self._git_available is None:
            self._git_available = shutil.which("git") is not None
            if not self._git_available:
                logger.warning("git not found in PATH, code versioning disabled")
        return self._git_available

    def _run_git(self, *args, check: bool = True) -> subprocess.CompletedProcess:
        """Run git command with GIT_DIR and GIT_WORK_TREE set."""
        env = os.environ.copy()
        env["GIT_DIR"] = self._git_dir
        env["GIT_WORK_TREE"] = self.project_root

        cmd = ["git"] + list(args)
        return subprocess.run(
            cmd,
            env=env,
            cwd=self.project_root,
            check=check,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _format_version(self, dt: datetime) -> str:
        """Format datetime as 'Version Dec 12, 8:45' (24h format)."""
        return f"Version {dt.strftime('%b')} {dt.day}, {dt.hour}:{dt.strftime('%M')}"

    def _ensure_git_initialized(self) -> bool:
        """Ensure the git repository is initialized. Returns True on success."""
        if self._git_initialized:
            return True

        if not self._is_git_available():
            return False

        try:
            # Check if already initialized
            if os.path.exists(os.path.join(self._git_dir, "HEAD")):
                self._git_initialized = True
                return True

            # Create git directory
            os.makedirs(self._git_dir, exist_ok=True)

            # Initialize repository
            self._run_git("init")

            # Configure user for commits (required by git)
            self._run_git("config", "user.name", "AO Code Versioner")
            self._run_git("config", "user.email", "ao@localhost")

            logger.info(f"Initialized git repository at {self._git_dir}")
            self._git_initialized = True
            return True

        except subprocess.SubprocessError as e:
            logger.error(f"Failed to initialize git repository: {e}")
            return False
        except OSError as e:
            logger.error(f"Failed to create git directory: {e}")
            return False

    def _commit_and_get_version(self) -> Optional[str]:
        """
        Commit tracked files and return version string.

        Uses only the files in self.tracked_files, ensuring git versioning
        and file watching are in sync.

        Returns:
            Human-readable version string like "Version Dec 12, 8:45", or None if unavailable.
        """
        if not self._ensure_git_initialized():
            return None

        try:
            files = list(self.tracked_files)
            if not files:
                logger.debug("No files to commit")
                return None

            # Stage only the files we're tracking
            self._run_git("add", "--", *files)

            # Check if there are staged changes
            result = self._run_git("diff", "--cached", "--quiet", check=False)

            if result.returncode == 0:
                # No changes - return timestamp of current HEAD if it exists
                try:
                    result = self._run_git("log", "-1", "--format=%cI", "HEAD")
                    timestamp_str = result.stdout.strip()
                    dt = datetime.fromisoformat(timestamp_str)
                    return self._format_version(dt)
                except subprocess.SubprocessError:
                    # No commits yet and no changes
                    return None

            # There are changes - commit them
            now = datetime.now()
            commit_message = now.isoformat(timespec="seconds")
            self._run_git("commit", "-m", commit_message)

            version_str = self._format_version(now)
            logger.info(f"Created git commit: {version_str}")
            return version_str

        except subprocess.SubprocessError as e:
            stderr = getattr(e, "stderr", None)
            logger.error(f"Git operation failed: {e}, stderr: {stderr}")
            return None
        except subprocess.TimeoutExpired:
            logger.error("Git operation timed out")
            return None

    def _handle_version_request(self, session_id: str) -> None:
        """Handle a request_version message: commit files and return version_date."""
        version_date = self._commit_and_get_version()
        if self.response_queue:
            self.response_queue.put(
                {
                    "type": "version_result",
                    "session_id": session_id,
                    "version_date": version_date,
                }
            )

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)

    def _log_tracked_files(self):
        """Log the current list of tracked files."""
        if not self.tracked_files:
            logger.info("Tracked files: (none)")
            return
        file_list = "\n  ".join(sorted(self.tracked_files))
        logger.info(f"Tracked files ({len(self.tracked_files)}):\n  {file_list}")

    def _scan_for_python_files(self) -> Set[str]:
        """
        Scan the project root for all Python files.

        Returns:
            Set of absolute paths to Python files (excluding .ao_rewritten.py files)
        """
        python_files = set()

        # Search for all .py files recursively from project root
        pattern = os.path.join(self.project_root, "**", "*.py")
        for file_path in glob.glob(pattern, recursive=True):
            # Skip .ao_rewritten.py debugging files
            if ".ao_rewritten" in file_path:
                continue

            # Skip files in __pycache__ directories
            if "__pycache__" in file_path:
                continue

            # Skip __init__.py - injecting imports causes circular import issues
            if os.path.basename(file_path) == "__init__.py":
                continue

            # Convert to absolute path
            abs_path = os.path.abspath(file_path)
            python_files.add(abs_path)

        return python_files

    def _update_tracked_files(self):
        """Discover new Python files and remove deleted ones."""
        discovered_files = self._scan_for_python_files()

        # Find new files to add
        new_files = discovered_files - self.tracked_files
        for new_file in new_files:
            self.tracked_files.add(new_file)
            logger.info(f"File added: {new_file}")
            try:
                if os.path.exists(new_file):
                    self.file_mtimes[new_file] = os.path.getmtime(new_file)
            except OSError as e:
                logger.error(f"Error accessing new file {new_file}: {e}")

        # Find deleted files to remove
        deleted_files = self.tracked_files - discovered_files
        for deleted_file in deleted_files:
            self.tracked_files.discard(deleted_file)
            self.file_mtimes.pop(deleted_file, None)
            logger.info(f"File removed: {deleted_file}")

            # Clean up associated .pyc file if it exists
            try:
                pyc_path = get_pyc_path(deleted_file)
                if os.path.exists(pyc_path):
                    os.remove(pyc_path)
            except OSError as e:
                logger.warning(f"Could not remove .pyc for {deleted_file}: {e}")

        if new_files or deleted_files:
            self._log_tracked_files()

    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self._shutdown = True

    def _is_parent_alive(self) -> bool:
        """Check if parent process is alive (PPID becomes 1 when parent dies)."""
        current_ppid = os.getppid()
        return current_ppid == self._parent_pid and current_ppid != 1

    def _start_parent_monitor(self) -> None:
        """Start a daemon thread that monitors if the parent process is still alive."""

        def monitor_parent():
            while not self._shutdown:
                if not self._is_parent_alive():
                    logger.info("Parent process died, shutting down...")
                    self._shutdown = True
                    return
                time.sleep(ORPHAN_POLL_INTERVAL)

        thread = threading.Thread(target=monitor_parent, daemon=True)
        thread.start()

    def _process_queue(self):
        """Process messages from MainServer (file paths or version requests)."""
        if not self.watch_queue:
            return

        added_files = []
        while True:
            try:
                msg = self.watch_queue.get_nowait()

                # Handle dict messages (structured commands)
                if isinstance(msg, dict):
                    msg_type = msg.get("type")
                    if msg_type == "request_version":
                        self._handle_version_request(msg.get("session_id"))
                    else:
                        logger.warning(f"Unknown message type: {msg_type}")
                    continue

                # Handle string messages (file paths from import hook)
                file_path = msg
                if file_path not in self.tracked_files:
                    self.tracked_files.add(file_path)
                    self.file_mtimes[file_path] = 0  # Force recompile
                    added_files.append(file_path)
                    logger.info(f"File added (import hook): {file_path}")
            except queue.Empty:
                break

        if added_files:
            self._log_tracked_files()

    def _needs_recompilation(self, file_path: str) -> bool:
        """Check if source is newer than cached .pyc."""
        try:
            if not os.path.exists(file_path):
                return False

            # Skip __init__.py files - they're loaded early during package initialization
            # and injecting imports can cause circular import errors
            if os.path.basename(file_path) == "__init__.py":
                return False

            pyc_path = get_pyc_path(file_path)
            # Check freshness: source mtime > pyc mtime means recompilation needed
            return os.path.getmtime(file_path) > os.path.getmtime(pyc_path)
        except OSError:
            # .pyc doesn't exist or other error - needs recompilation
            return True

    def _compile_file(self, file_path: str) -> bool:
        """Compile a single file with AST rewrites to .pyc format."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()

            # Apply AST rewrites and compile to code object
            debug_ast = os.environ.get("DEBUG_AST_REWRITES")
            if debug_ast and ".ao_rewritten.py" not in file_path:
                code_object, tree = rewrite_source_to_code(
                    source, file_path, user_files=self.tracked_files, return_tree=True
                )
                # Write transformed source to .ao_rewritten.py for debugging
                debug_path = file_path.replace(".py", ".ao_rewritten.py")
                try:
                    rewritten_source = ast.unparse(tree)
                    with open(debug_path, "w", encoding="utf-8") as f:
                        f.write(rewritten_source)
                except Exception as e:
                    logger.error(f"Failed to write debug AST: {e}")
            else:
                code_object = rewrite_source_to_code(
                    source, file_path, user_files=self.tracked_files
                )

            pyc_path = get_pyc_path(file_path)

            # Ensure cache directory exists
            os.makedirs(os.path.dirname(pyc_path), exist_ok=True)

            # Write .pyc file manually (py_compile would recompile without our AST rewrites)
            import marshal
            import struct
            import importlib.util

            source_mtime = int(os.path.getmtime(file_path))
            source_size = os.path.getsize(file_path)

            with open(pyc_path, "wb") as f:
                f.write(importlib.util.MAGIC_NUMBER)
                f.write(struct.pack("<I", 0))  # flags
                f.write(struct.pack("<I", source_mtime))
                f.write(struct.pack("<I", source_size))
                f.write(marshal.dumps(code_object))

            if not os.path.exists(pyc_path):
                logger.error(f"✗ .pyc not created: {pyc_path}")
                return False

            self.file_mtimes[file_path] = os.path.getmtime(file_path)
            logger.info(f"Recompiled {file_path}")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to compile {file_path}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def check_and_recompile(self):
        """Check all tracked files and recompile those that have changed."""
        self._process_queue()
        self._update_tracked_files()

        for file_path in self.tracked_files:
            if self._shutdown:
                return
            if self._needs_recompilation(file_path):
                self._compile_file(file_path)

    def run(self):
        """Main polling loop that monitors files and triggers recompilation."""
        # Start parent monitor thread (detects orphaned process)
        self._start_parent_monitor()

        # Polling loop
        try:
            while not self._shutdown:
                self.check_and_recompile()
                time.sleep(FILE_POLL_INTERVAL)
        except Exception:
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        finally:
            logger.info(f"File watcher process {self.pid} exiting")


def run_file_watcher_process(project_root: str = None, watch_queue=None, response_queue=None):
    """
    Entry point for the file watcher process.

    This function is called when the file watcher runs as a separate process.
    It creates a FileWatcher instance and starts the monitoring loop.

    Args:
        project_root: Root directory to scan for Python files (from VS Code workspace)
        watch_queue: multiprocessing.Queue for receiving messages from MainServer
        response_queue: multiprocessing.Queue for sending messages back to MainServer
    """
    watcher = FileWatcher(project_root, watch_queue, response_queue)
    watcher.run()


# Pre-compute version tag (called many times, never changes)
_VERSION_TAG = f"cpython-{sys.version_info.major}{sys.version_info.minor}"


def get_pyc_path(py_file_path: str) -> str:
    """
    Generate the .pyc file path for AST-rewritten code.

    All compiled files go to centralized cache at ~/.cache/ao/pyc/.
    Uses hash of full source path to avoid collisions and path length issues.

    Args:
        py_file_path: Path to the .py source file

    Returns:
        Path where the .pyc file should be written in ~/.cache/ao/pyc/
    """
    # Hash the full path to ensure uniqueness and avoid path length issues
    path_hash = hashlib.md5(py_file_path.encode()).hexdigest()[:16]
    base_name = os.path.splitext(os.path.basename(py_file_path))[0]
    pyc_name = f"{base_name}.{path_hash}.{_VERSION_TAG}.pyc"
    return os.path.join(AO_CACHE_DIR, pyc_name)
