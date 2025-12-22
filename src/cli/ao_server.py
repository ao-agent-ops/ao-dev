# Register taint functions in builtins BEFORE any other imports
# This ensures any rewritten .pyc files can call these functions
import builtins
import sys
import os

# Add current directory to path to import modules directly
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import directly from file path to avoid triggering ao.__init__.py
import importlib.util

ast_helpers_path = os.path.join(current_dir, "server", "ast_helpers.py")
spec = importlib.util.spec_from_file_location("ast_helpers", ast_helpers_path)
ast_helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ast_helpers)

builtins.taint_fstring_join = ast_helpers.taint_fstring_join
builtins.taint_format_string = ast_helpers.taint_format_string
builtins.taint_percent_format = ast_helpers.taint_percent_format
builtins.exec_func = ast_helpers.exec_func

# Now safe to import other modules
import socket
import time
import subprocess
from argparse import ArgumentParser
from ao.common.logger import logger
from ao.common.constants import AO_LOG_PATH, HOST, PORT, SOCKET_TIMEOUT, SHUTDOWN_WAIT
from ao.server.develop_server import DevelopServer, send_json


def launch_daemon_server() -> None:
    """
    Launch the develop server as a detached daemon process with proper stdio handling.
    """
    # Create log file path
    log_file = AO_LOG_PATH

    # Ensure log directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Open log file for the daemon
    with open(log_file, "a+") as log_f:
        subprocess.Popen(
            [sys.executable, "-m", "ao.cli.ao_server", "_serve"],
            close_fds=True,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=subprocess.STDOUT,  # Combine stderr with stdout
        )


def server_command_parser():
    parser = ArgumentParser(
        usage="ao-server {start, stop, restart, clear, logs, clear-logs}",
        description="Server utilities.",
        allow_abbrev=False,
    )

    parser.add_argument(
        "command",
        choices=["start", "stop", "restart", "clear", "logs", "clear-logs", "_serve"],
        help="The command to execute for the server.",
    )
    return parser


def execute_server_command(args):
    if args.command == "start":
        # If server is already running, do not start another
        try:
            socket.create_connection((HOST, PORT), timeout=SOCKET_TIMEOUT).close()
            logger.info("Develop server is already running.")
            return
        except Exception:
            pass
        # Launch the server as a detached background process (POSIX)
        launch_daemon_server()
        logger.info("Develop server started.")

    elif args.command == "stop":
        # Connect to the server and send a shutdown command
        try:
            sock = socket.create_connection((HOST, PORT), timeout=SOCKET_TIMEOUT)
            handshake = {"type": "hello", "role": "admin", "script": "stopper"}
            send_json(sock, handshake)
            send_json(sock, {"type": "shutdown"})
            sock.close()
            logger.info("Develop server stop signal sent.")
        except Exception:
            logger.warning("No running server found.")
            sys.exit(1)

    elif args.command == "restart":
        # Stop the server if running
        # TODO: Delete previour server log.
        try:
            sock = socket.create_connection((HOST, PORT), timeout=SOCKET_TIMEOUT)
            handshake = {"type": "hello", "role": "admin", "script": "restarter"}
            send_json(sock, handshake)
            send_json(sock, {"type": "shutdown"})
            sock.close()
            logger.info("Develop server stop signal sent (for restart). Waiting for shutdown...")
            time.sleep(SHUTDOWN_WAIT)
        except Exception:
            logger.info("No running server found. Proceeding to start.")
        # Start the server
        launch_daemon_server()
        logger.info("Develop server restarted.")

    elif args.command == "clear":
        # Connect to the server and send a clear command
        # TODO: Delete previour server log.
        try:
            sock = socket.create_connection((HOST, PORT), timeout=SOCKET_TIMEOUT)
            handshake = {"type": "hello", "role": "admin", "script": "clearer"}
            send_json(sock, handshake)
            send_json(sock, {"type": "clear"})
            sock.close()
            logger.info("Develop server clear signal sent.")
        except Exception:
            logger.warning("No running server found.")
            sys.exit(1)
        return

    elif args.command == "logs":
        # Print the contents of the server log file
        try:
            with open(AO_LOG_PATH, "r") as log_file:
                print(log_file.read(), end="")
        except FileNotFoundError:
            print(f"Log file not found at {AO_LOG_PATH}")
        except Exception as e:
            print(f"Error reading log file: {e}")
        return

    elif args.command == "clear-logs":
        # Clear the contents of the server log file
        try:
            # Ensure log directory exists
            os.makedirs(os.path.dirname(AO_LOG_PATH), exist_ok=True)
            # Clear the log file by opening in write mode
            with open(AO_LOG_PATH, "w") as log_file:
                pass  # Opening in 'w' mode truncates the file
            logger.info("Server log file cleared.")
        except Exception as e:
            logger.error(f"Error clearing log file: {e}")
            sys.exit(1)
        return

    elif args.command == "_serve":
        # Internal: run the server loop (not meant to be called by users directly)
        server = DevelopServer()
        server.run_server()


def main():
    parser = server_command_parser()
    args = parser.parse_args()
    execute_server_command(args)


if __name__ == "__main__":
    main()
