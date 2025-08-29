"""
Monkey patches for built-in file operations to enable taint tracking.
"""

import builtins
import io
from functools import wraps
from runner.taint_wrappers import TaintFile


def patch_builtin_open():
    """
    Patch the built-in open() function to automatically wrap files with TaintFile
    for taint tracking across sessions.
    """
    from common.logger import logger
    logger.debug("Patching built-in open() function")
    original_open = builtins.open
    
    @wraps(original_open)
    def patched_open(file, mode='r', *args, **kwargs):
        from common.logger import logger
        logger.debug(f"patched_open called: file={file}, mode={mode}")
        # Call the original open function
        file_obj = original_open(file, mode, *args, **kwargs)
        
        # Wrap the file object with TaintFile for taint tracking
        # Only wrap text mode files, not binary mode
        if 'b' not in mode:
            # Get session ID from environment (set by the runner)
            import os
            session_id = os.environ.get('AGENT_COPILOT_SESSION_ID')
            
            # Determine if this is a read or write mode
            if any(m in mode for m in ['r', 'r+']):
                # For reading, we want to retrieve taint from previous sessions
                taint_origin = f"file:{file}"
            elif any(m in mode for m in ['w', 'a', 'x', 'w+', 'a+', 'x+']):
                # For writing, we'll track what's written
                taint_origin = None  # Will be determined by what's written
            else:
                taint_origin = f"file:{file}"
            
            # Get the file mode from the file object
            file_mode = getattr(file_obj, 'mode', mode)
            
            # Wrap with TaintFile
            logger.debug(f"Wrapping {file} with TaintFile, session_id={session_id}")
            taint_file = TaintFile(file_obj, mode=file_mode, taint_origin=taint_origin, session_id=session_id)
            return taint_file
        
        # Return binary files as-is for now
        return file_obj
    
    # Replace the built-in open
    builtins.open = patched_open
    
    # Also patch io.open which is sometimes used directly
    io.open = patched_open


def apply_file_patches():
    """Apply all file-related patches."""
    from common.logger import logger
    logger.debug("apply_file_patches called - about to patch built-in open()")
    patch_builtin_open()
    logger.debug("File patches applied successfully")