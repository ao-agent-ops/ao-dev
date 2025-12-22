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
from typing import Dict, Set
from ao.common.logger import logger
from ao.common.constants import FILE_POLL_INTERVAL, AO_PROJECT_ROOT
from ao.server.ast_transformer import TaintPropagationTransformer
from ao.common.utils import MODULES_TO_FILES


def rewrite_source_to_code(
    source: str, filename: str, module_to_file: dict = None, return_tree=False
):
    """
    Transform and compile Python source code with AST rewrites.

    This is a pure function that applies AST transformations and compiles
    the result to a code object. Same input always produces same output,
    making it suitable for caching.

    Args:
        source: Python source code as a string
        filename: Path to the source file (used in error messages and code object)
        module_to_file: Dict mapping user module names to their file paths.
                       Used to distinguish user code from third-party code.
        return_tree: If True, return (code_object, tree) tuple for debugging

    Returns:
        A compiled code object ready for execution, or (code_object, tree) if return_tree=True

    Raises:
        SyntaxError: If the source code is invalid
        Exception: If AST transformation fails
    """
    # Inject future imports to prevent type annotations from being evaluated at import time
    # This must be done before parsing to avoid AST transformation of type subscripts
    if "from __future__ import annotations" not in source:
        source = "from __future__ import annotations\n" + source

    # Parse source into AST
    tree = ast.parse(source, filename=filename)

    # Apply AST transformations and inject imports if needed
    transformer = TaintPropagationTransformer(module_to_file=module_to_file, current_file=filename)
    tree = transformer.visit(tree)
    tree = transformer._inject_taint_imports(tree)
    ast.fix_missing_locations(tree)

    # Compile to code object
    code_object = compile(tree, filename, "exec")

    if return_tree:
        return code_object, tree
    return code_object


def is_pyc_rewritten(pyc_path: str) -> bool:
    """
    Check if a .pyc file was created by our AST transformer.

    Returns True if the .pyc contains our injected imports (exec_func, etc).
    Files with no transformations (empty __init__.py) return False, which is fine -
    they don't need special handling.
    """
    try:
        import marshal

        with open(pyc_path, "rb") as f:
            f.read(16)  # Skip .pyc header
            code = marshal.load(f)
            # Check for our injected function names
            return "exec_func" in code.co_names or "taint_fstring_join" in code.co_names
    except Exception:
        return False


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
        self.project_root = AO_PROJECT_ROOT  # Use project root from config
        self._populate_initial_mtimes()
        self._setup_signal_handlers()

    def _populate_initial_mtimes(self):
        """Initialize modification times for all tracked files."""
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
            # Skip .ao_rewritten.py files (these are debugging files, not real code)
            if ".ao_rewritten" in file_path:
                continue

            # Skip files in __pycache__ directories
            if "__pycache__" in file_path:
                continue

            # Convert to absolute path
            abs_path = os.path.abspath(file_path)
            python_files.add(abs_path)

        return python_files

    def _generate_module_name(self, file_path: str) -> str:
        """
        Generate a module name for a discovered Python file.

        Args:
            file_path: Absolute path to the Python file

        Returns:
            Module name suitable for the module_to_file mapping
        """
        # Get relative path from project root
        rel_path = os.path.relpath(file_path, self.project_root)

        # Convert path separators to dots and remove .py extension
        module_name = rel_path.replace(os.sep, ".").replace(".py", "")

        # Handle special cases like __init__.py
        if module_name.endswith(".__init__"):
            module_name = module_name[:-9]  # Remove .__init__

        return module_name

    def _update_tracked_files(self):
        """
        Update the tracked files by discovering new Python files and removing deleted ones.
        """
        discovered_files = self._scan_for_python_files()
        current_tracked_files = set(self.module_to_file.values())

        # Find new files to add
        new_files = discovered_files - current_tracked_files
        for new_file in new_files:
            module_name = self._generate_module_name(new_file)
            self.module_to_file[module_name] = new_file
            # Also update the global MODULES_TO_FILES singleton
            MODULES_TO_FILES[module_name] = new_file

            # Initialize mtime for the new file
            try:
                if os.path.exists(new_file):
                    mtime = os.path.getmtime(new_file)
                    self.file_mtimes[new_file] = mtime
            except OSError as e:
                logger.error(f"[FileWatcher] Error accessing new file {new_file}: {e}")

        # Find deleted files to remove
        deleted_files = current_tracked_files - discovered_files
        for deleted_file in deleted_files:
            # Remove from module_to_file mapping
            modules_to_remove = [
                mod for mod, path in self.module_to_file.items() if path == deleted_file
            ]
            for module_name in modules_to_remove:
                del self.module_to_file[module_name]
                # Also remove from the global MODULES_TO_FILES singleton
                if module_name in MODULES_TO_FILES:
                    del MODULES_TO_FILES[module_name]

            # Remove from mtime tracking
            if deleted_file in self.file_mtimes:
                del self.file_mtimes[deleted_file]

            # Clean up associated .pyc file if it exists
            try:
                pyc_path = get_pyc_path(deleted_file)
                if os.path.exists(pyc_path):
                    os.remove(pyc_path)
            except OSError as e:
                logger.warning(f"[FileWatcher] Could not remove .pyc file for {deleted_file}: {e}")

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

            # Skip __init__.py files - they're loaded early during package initialization
            # and injecting imports can cause circular import errors
            if os.path.basename(file_path) == "__init__.py":
                return False

            # Check if .pyc file exists
            pyc_path = get_pyc_path(file_path)
            if not os.path.exists(pyc_path):
                return True

            # Check if the .pyc file was created by our AST transformer
            if not is_pyc_rewritten(pyc_path):
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
            debug_ast = os.environ.get("AO_DEBUG_AST_REWRITES")
            if debug_ast and not ".AO_rewritten.py" in file_path:
                code_object, tree = rewrite_source_to_code(
                    source, file_path, module_to_file=self.module_to_file, return_tree=True
                )
                # Write transformed source to .ao_rewritten.py for debugging
                import ast

                debug_path = file_path.replace(".py", ".ao_rewritten.py")
                try:
                    rewritten_source = ast.unparse(tree)
                    with open(debug_path, "w", encoding="utf-8") as f:
                        f.write(rewritten_source)
                except Exception as e:
                    logger.error(f"[FileWatcher] Failed to write debug AST: {e}")
            else:
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
            if not os.path.exists(pyc_path):
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
        Also discovers new files and handles deleted files.

        This method is called periodically by the polling loop to detect
        and handle file changes.
        """
        # First, update the list of tracked files (discover new, remove deleted)
        self._update_tracked_files()

        # Then check existing files for changes
        for module_name, file_path in self.module_to_file.items():
            if self._shutdown:
                return
            if self._needs_recompilation(file_path):
                self._compile_file(file_path, module_name)

    def run(self):
        """
        Main polling loop that monitors files and triggers recompilation.

        This method runs until a shutdown signal is received, checking for
        file changes every FILE_POLL_INTERVAL seconds and recompiling changed files.
        """
        # Initial compilation of all files
        compiled_count = 0
        failed_count = 0
        for module_name, file_path in self.module_to_file.items():
            if self._shutdown:
                return
            if self._needs_recompilation(file_path):
                if self._compile_file(file_path, module_name):
                    compiled_count += 1
                else:
                    failed_count += 1

        # Start polling loop
        try:
            while not self._shutdown:
                self.check_and_recompile()
                time.sleep(FILE_POLL_INTERVAL)
        except Exception as e:
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
    Generate the .pyc file path for AST-rewritten code.

    Args:
        py_file_path: Path to the .py source file

    Returns:
        Path where the .pyc file should be written
    """
    dir_name = os.path.dirname(py_file_path)
    base_name = os.path.splitext(os.path.basename(py_file_path))[0]
    cache_dir = os.path.join(dir_name, "__ao_cache__")

    # Include Python version in filename (e.g., module.cpython-311.pyc)
    version_tag = f"cpython-{sys.version_info.major}{sys.version_info.minor}"
    pyc_name = f"{base_name}.{version_tag}.pyc"

    return os.path.join(cache_dir, pyc_name)
