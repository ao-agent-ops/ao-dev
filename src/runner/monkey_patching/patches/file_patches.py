"""
Monkey patches for built-in file operations to enable taint tracking.
"""

import builtins
import io
from functools import wraps
from aco.runner.taint_wrappers import TaintFile


def _should_wrap_file(file_path):
    """
    Determine if a file should be wrapped with TaintFile based on its path.
    Only wrap user files that are likely to be involved in LLM data flow.
    NOTE: this is a hack.
    """
    import os
    import sys

    # Convert to absolute path for consistent checking
    try:
        abs_path = os.path.abspath(str(file_path))
    except:
        # If we can't get absolute path, don't wrap
        return False

    # Don't wrap system/library files
    system_dirs = [
        "/System/",
        "/Library/",
        "/usr/",
        "/opt/",
        sys.prefix,  # Python installation directory
        os.path.dirname(sys.executable),  # Python executable directory
    ]

    # Add site-packages and dist-packages paths
    for path in sys.path:
        if "site-packages" in path or "dist-packages" in path:
            system_dirs.append(path)

    # Check if file is in any system directory
    for sys_dir in system_dirs:
        if sys_dir and abs_path.startswith(sys_dir):
            return False

    # Don't wrap temporary or cache files
    temp_patterns = [
        "/tmp/",
        "/var/tmp/",
        ".cache/",
        "__pycache__/",
        ".git/",
        "/temp/",
        ".tmp",
        ".log",
    ]

    for pattern in temp_patterns:
        if pattern in abs_path:
            return False

    # Don't wrap certain file extensions that are unlikely to contain taint
    _, ext = os.path.splitext(abs_path)
    skip_extensions = {
        ".pyc",
        ".pyo",
        ".pyd",
        ".so",
        ".dylib",
        ".dll",
        ".zip",
        ".egg",
        ".whl",
        ".jar",
        ".json",
        ".yaml",
        ".yml",
        ".ini",
        ".cfg",
        ".conf",
        ".lock",
        ".pid",
        ".db",
        ".sqlite",
        ".sqlite3",
    }

    if ext.lower() in skip_extensions:
        return False

    # Only wrap files in the current working directory or subdirectories
    # This catches user project files
    try:
        cwd = os.getcwd()
        if abs_path.startswith(cwd):
            return True
    except:
        pass

    # Don't wrap anything else
    return False


def patch_builtin_open():
    """
    Patch the built-in open() function to automatically wrap files with TaintFile
    for taint tracking across sessions.
    """
    from aco.common.logger import logger

    logger.debug("Patching built-in open() function")
    original_open = builtins.open

    @wraps(original_open)
    def patched_open(file, mode="r", *args, **kwargs):
        from aco.common.logger import logger

        # Call the original open function first
        file_obj = original_open(file, mode, *args, **kwargs)

        # Only wrap text mode files that are user files
        if "b" not in mode and _should_wrap_file(file):
            logger.debug(f"patched_open: Wrapping user file {file} with TaintFile, mode={mode}")

            # Get session ID from environment (set by the runner)
            import os

            session_id = os.environ.get("AGENT_COPILOT_SESSION_ID")

            # Determine if this is a read or write mode
            if any(m in mode for m in ["r", "r+"]):
                # For reading, we want to retrieve taint from previous sessions
                taint_origin = f"file:{file}"
            elif any(m in mode for m in ["w", "a", "x", "w+", "a+", "x+"]):
                # For writing, we'll track what's written
                taint_origin = None  # Will be determined by what's written
            else:
                taint_origin = f"file:{file}"

            # Get the file mode from the file object
            file_mode = getattr(file_obj, "mode", mode)

            # Wrap with TaintFile
            taint_file = TaintFile(
                file_obj, mode=file_mode, taint_origin=taint_origin, session_id=session_id
            )
            return taint_file
        else:
            # Don't wrap: binary files, system files, or library files
            if "b" not in mode:  # Only log for text files we're skipping
                logger.debug(f"patched_open: Skipping system/library file {file}")

        # Return unwrapped file object
        return file_obj

    # Replace the built-in open
    builtins.open = patched_open

    # Also patch io.open which is sometimes used directly
    io.open = patched_open


def apply_file_patches():
    """Apply all file-related patches."""
    from aco.common.logger import logger

    logger.debug("apply_file_patches called - about to patch built-in open()")
    patch_builtin_open()
    logger.debug("File patches applied successfully")
