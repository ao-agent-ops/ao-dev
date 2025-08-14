import logging


def setup_logging():
    # Clear out any old handlers (especially in REPL or interactive walks)
    root = logging.getLogger("ACO")
    if root.handlers:
        root.handlers.clear()

    root.setLevel(logging.DEBUG)
    # Create a console handler
    console_handler = logging.StreamHandler()

    # Create and set a formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)

    # Add handler to logger
    root.addHandler(console_handler)
    return root


logger = setup_logging()
