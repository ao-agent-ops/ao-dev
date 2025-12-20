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

import os
import sys
import time
import signal
from typing import Dict
from ao.common.logger import logger
from ao.common.constants import FILE_POLL_INTERVAL
from ao.server.ast_transformer import rewrite_source_to_code


class FileWatcher:
    """
    Monitors user module files and precompiles them with AST rewrites.

    This class tracks modification times of user modules and automatically
    recompiles them to .pyc files when changes are detected. The compiled
    .pyc files contain the AST-rewritten code with taint propagation.
    """

    def __init__(self, module_to_file: Dict[str, str]):
        """
        Initialize the file watcher.

        Args:
            module_to_file: Dict mapping module names to their file paths
                           (e.g., {"mypackage.mymodule": "/path/to/mymodule.py"})
        """
        self.module_to_file = module_to_file
        self.file_mtimes = {}  # Track last modification times
        self.pid = os.getpid()
        self._shutdown = False  # Flag to signal shutdown
        self._populate_initial_mtimes()
        self._setup_signal_handlers()

    def _populate_initial_mtimes(self):
        """Initialize modification times for all tracked files."""
        logger.debug(f"[FileWatcher] Initializing tracking for {len(self.module_to_file)} modules")
        for module_name, file_path in self.module_to_file.items():
            try:
                if os.path.exists(file_path):
                    mtime = os.path.getmtime(file_path)
                    self.file_mtimes[file_path] = mtime
                else:
                    logger.warning(
                        f"[FileWatcher] Module file not found: {module_name} -> {file_path}"
                    )
            except OSError as e:
                logger.error(f"[FileWatcher] Error accessing file {file_path}: {e}")

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        logger.debug(f"[FileWatcher] Signal handlers installed for pid {self.pid}")

    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"[FileWatcher] Received signal {signum}, shutting down gracefully...")
        self._shutdown = True

    def _needs_recompilation(self, file_path: str) -> bool:
        """
        Check if a file needs recompilation based on modification time, missing .pyc file,
        or if the .pyc file wasn't created by our AST transformer.

        Args:
            file_path: Path to the source file

        Returns:
            True if the file needs recompilation, False otherwise
        """
        try:
            if not os.path.exists(file_path):
                return False

            # Check if .pyc file exists
            pyc_path = get_pyc_path(file_path)
            if not os.path.exists(pyc_path):
                return True

            # Check if the .pyc file was created by our AST transformer
            from ao.server.ast_transformer import is_pyc_rewritten

            if not is_pyc_rewritten(pyc_path):
                logger.debug(
                    f"[FileWatcher] .pyc file {pyc_path} not rewritten, forcing recompilation"
                )
                return True

            current_mtime = os.path.getmtime(file_path)
            last_mtime = self.file_mtimes.get(file_path, 0)

            return current_mtime > last_mtime
        except OSError as e:
            logger.error(f"Error checking modification time for {file_path}: {e}")
            return False

    def _compile_file(self, file_path: str, module_name: str) -> bool:
        """
        Compile a single file with AST rewrites to .pyc format.

        Args:
            file_path: Path to the source file
            module_name: Name of the module

        Returns:
            True if compilation succeeded, False otherwise
        """
        try:
            # Read source code
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()

            # Apply AST rewrites and compile to code object
            code_object = rewrite_source_to_code(
                source, file_path, module_to_file=self.module_to_file
            )

            # Get target .pyc path
            pyc_path = get_pyc_path(file_path)

            # Ensure __pycache__ directory exists
            cache_dir = os.path.dirname(pyc_path)
            os.makedirs(cache_dir, exist_ok=True)

            # Write compiled code to .pyc file
            # We need to write the .pyc file manually since py_compile.compile()
            # would recompile from source without our AST rewrites
            import marshal
            import struct
            import importlib.util

            source_mtime = int(os.path.getmtime(file_path))
            source_size = os.path.getsize(file_path)

            # .pyc file format: magic number + flags + timestamp + source size + marshaled code
            with open(pyc_path, "wb") as f:
                # Write magic number for current Python version
                f.write(importlib.util.MAGIC_NUMBER)

                # Write flags (0 for now)
                f.write(struct.pack("<I", 0))

                # Write source file timestamp
                f.write(struct.pack("<I", source_mtime))

                # Write source file size
                f.write(struct.pack("<I", source_size))

                # Write marshaled code object
                f.write(marshal.dumps(code_object))

            # Verify .pyc file was created
            if os.path.exists(pyc_path):
                pyc_size = os.path.getsize(pyc_path)
                # Compilation successful
            else:
                logger.error(f"[FileWatcher] ✗ .pyc file was not created: {pyc_path}")
                return False

            # Update our tracked modification time
            self.file_mtimes[file_path] = os.path.getmtime(file_path)

            return True

        except Exception as e:
            logger.error(f"[FileWatcher] ✗ Failed to compile {module_name} at {file_path}: {e}")
            import traceback

            logger.error(f"[FileWatcher] Traceback: {traceback.format_exc()}")
            return False

    def check_and_recompile(self):
        """
        Check all tracked files and recompile those that have changed.

        This method is called periodically by the polling loop to detect
        and handle file changes.
        """
        for module_name, file_path in self.module_to_file.items():
            if self._shutdown:
                return
            if self._needs_recompilation(file_path):
                logger.debug(f"File changed, recompiling: {file_path}")
                self._compile_file(file_path, module_name)

    def run(self):
        """
        Main polling loop that monitors files and triggers recompilation.

        This method runs until a shutdown signal is received, checking for
        file changes every FILE_POLL_INTERVAL seconds and recompiling changed files.
        """
        logger.debug(f"[FileWatcher] Starting file watcher process")

        # Initial compilation of all files
        compiled_count = 0
        failed_count = 0
        for module_name, file_path in self.module_to_file.items():
            if self._shutdown:
                logger.info("[FileWatcher] Shutdown requested during initial compilation")
                return
            if self._compile_file(file_path, module_name):
                compiled_count += 1
            else:
                failed_count += 1

        logger.info(
            f"[FileWatcher] Initial compilation complete: {compiled_count} successful, {failed_count} failed"
        )

        # Start polling loop
        try:
            logger.info("[FileWatcher] Starting polling loop...")
            while not self._shutdown:
                self.check_and_recompile()
                time.sleep(FILE_POLL_INTERVAL)
        except KeyboardInterrupt:
            logger.info("[FileWatcher] File watcher stopped by user")
        except Exception as e:
            logger.error(f"[FileWatcher] File watcher error: {e}")
            import traceback

            logger.error(f"[FileWatcher] Traceback: {traceback.format_exc()}")
            raise
        finally:
            logger.info(f"[FileWatcher] File watcher process {self.pid} exiting")


def run_file_watcher_process(module_to_file: Dict[str, str]):
    """
    Entry point for the file watcher process.

    This function is called when the file watcher runs as a separate process.
    It creates a FileWatcher instance and starts the monitoring loop.

    Args:
        module_to_file: Dict mapping module names to their file paths
    """
    watcher = FileWatcher(module_to_file)
    watcher.run()


def get_pyc_path(py_file_path: str) -> str:
    """
    Generate the standard .pyc file path for a given .py file.

    Args:
        py_file_path: Path to the .py source file

    Returns:
        Path where the .pyc file should be written
    """
    # Python's standard __pycache__ naming convention
    dir_name = os.path.dirname(py_file_path)
    base_name = os.path.splitext(os.path.basename(py_file_path))[0]
    cache_dir = os.path.join(dir_name, "__pycache__")

    # Include Python version in filename (e.g., module.cpython-311.pyc)
    version_tag = f"cpython-{sys.version_info.major}{sys.version_info.minor}"
    pyc_name = f"{base_name}.{version_tag}.pyc"

    return os.path.join(cache_dir, pyc_name)
