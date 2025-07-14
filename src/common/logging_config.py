import logging

def setup_logging():
    # Clear out any old handlers (especially in REPL or interactive walks)
    root = logging.getLogger()
    if root.handlers:
        root.handlers.clear()

    # Attach a default StreamHandler to stderr
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
    )

    return root
