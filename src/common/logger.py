import logging
import os


def setup_logger():
    # Clear out any old handlers (especially in REPL or interactive walks)
    root = logging.getLogger("ACO")
    if root.handlers:
        root.handlers.clear()

    root.setLevel(logging.DEBUG)

    # Create a console handler
    handler = logging.StreamHandler()

    # Create and set a formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    # Add handler to logger
    root.addHandler(handler)
    return root


def setup_file_logger(name: str, log_file_path: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Set up a logger that writes to both a file and console.
    
    Args:
        name: Name of the logger (e.g., "FileWatcher", "OptimizationServer")
        log_file_path: Path to the log file
        level: Logging level (default: DEBUG)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Clear any existing handlers
    if logger.handlers:
        logger.handlers.clear()

    logger.setLevel(level)

    # Create file handler
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    file_handler = logging.FileHandler(log_file_path, mode="a")

    # Create console handler  
    console_handler = logging.StreamHandler()

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()
