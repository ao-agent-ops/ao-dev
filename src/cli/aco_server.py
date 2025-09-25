import sys
import socket
import time
import subprocess
import os
from argparse import ArgumentParser
from aco.common.logger import logger
from aco.common.constants import ACO_LOG_PATH, HOST, PORT, SOCKET_TIMEOUT, SHUTDOWN_WAIT
from aco.server.develop_server import DevelopServer, send_json


def launch_daemon_server() -> None:
    """
    Launch the develop server as a detached daemon process with proper stdio handling.
    """
    # Create log file path
    log_file = ACO_LOG_PATH

    # Ensure log directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # Open log file for the daemon
    with open(log_file, "a+") as log_f:
        subprocess.Popen(
            [sys.executable, "-m", "aco.cli.aco_server", "_serve"],
            close_fds=True,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log_f,
            stderr=subprocess.STDOUT,  # Combine stderr with stdout
        )


def server_command_parser():
    parser = ArgumentParser(
        usage="aco-server {start, stop, restart, clear}",
        description="Server utilities.",
        allow_abbrev=False,
    )

    parser.add_argument(
        "command",
        choices=["start", "stop", "restart", "clear", "_serve"],
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
