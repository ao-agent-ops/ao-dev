#!/usr/bin/env python3

import sys
import os
import socket
import json
import random
import threading
import time
import psutil
import debugpy
import signal
import runpy
import builtins
from contextvars import ContextVar
from typing import Optional, List

from aco.common.logger import logger
from aco.common.constants import (
    HOST,
    PORT,
    CONNECTION_TIMEOUT,
    SERVER_START_TIMEOUT,
    SERVER_START_WAIT,
)
from aco.common.utils import MODULES_TO_FILES
from aco.cli.aco_server import launch_daemon_server
from aco.runner.ast_rewrite_hook import install_patch_hook, set_module_to_user_file
from aco.runner.context_manager import set_parent_session_id, set_server_connection
from aco.runner.monkey_patching.apply_monkey_patches import apply_all_monkey_patches
from aco.server.ast_helpers import (
    taint_fstring_join,
    taint_format_string,
    taint_percent_format,
    taint_open,
    exec_func,
    exec_setitem,
    exec_delitem,
    exec_inplace_binop,
    wrap_assign,
    get_attr,
    get_item,
    set_attr,
    wrap_if_needed,
    add_to_taint_dict_and_return,
    get_taint,
)
from aco.server.database_manager import DB


def get_runner_dir():
    """Return the absolute path to the runner directory."""
    return os.path.abspath(os.path.dirname(__file__))


def _log_error(context: str, exception: Exception) -> None:
    """Centralized error logging utility."""
    import traceback

    logger.error(f"[AgentRunner] {context}: {exception}")
    logger.debug(f"[AgentRunner] Traceback: {traceback.format_exc()}")


def ensure_server_running() -> None:
    """Ensure the develop server is running, start it if necessary."""
    try:
        socket.create_connection((HOST, PORT), timeout=SERVER_START_TIMEOUT).close()
        logger.debug(f"Server already running on {HOST}:{PORT}")
    except Exception:
        logger.info(f"Starting server on {HOST}:{PORT}")
        launch_daemon_server()
        time.sleep(SERVER_START_WAIT)
        socket.create_connection((HOST, PORT), timeout=CONNECTION_TIMEOUT).close()
        logger.debug("Server started successfully")


class AgentRunner:
    """Unified agent runner that combines orchestration and execution in a single process."""

    def __init__(
        self,
        script_path: str,
        script_args: List[str],
        is_module_execution: bool,
        project_root: str,
        sample_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.script_path = script_path
        self.script_args = script_args
        self.is_module_execution = is_module_execution
        self.project_root = project_root
        self.sample_id = sample_id
        self.user_id = user_id

        # State management
        self.shutdown_flag = False
        self.process_id = os.getpid()

        # Server communication
        self.session_id: Optional[str] = None
        self.server_conn: Optional[socket.socket] = None

        # Threading for server messages
        self.listener_thread: Optional[threading.Thread] = None

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _send_message(self, msg_type: str, **kwargs) -> None:
        """Send a message to the develop server."""
        if not self.server_conn:
            return
        message = {"type": msg_type, "role": "agent-runner", **kwargs}
        if self.session_id:
            message["session_id"] = self.session_id
        try:
            self.server_conn.sendall((json.dumps(message) + "\n").encode("utf-8"))
        except Exception as e:
            _log_error("Failed to send message to server", e)

    def send_deregister(self) -> None:
        """Send deregistration message to the develop server."""
        self._send_message("deregister")

    def _signal_handler(self, signum, frame) -> None:
        """Handle termination signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.send_deregister()
        if self.server_conn:
            try:
                self.server_conn.close()
            except Exception as e:
                _log_error("Error closing server connection", e)
        sys.exit(0)

    def _listen_for_server_messages(self, sock: socket.socket) -> None:
        """Background thread: listen for 'restart' or 'shutdown' messages from the server."""
        try:
            sock.setblocking(False)
            buffer = b""
            while not self.shutdown_flag:
                try:
                    import select

                    rlist, _, _ = select.select([sock], [], [], 1.0)
                    if rlist:
                        data = sock.recv(4096)
                        if not data:
                            break
                        buffer += data
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            try:
                                msg = json.loads(line.decode("utf-8").strip())
                                self._handle_server_message(msg)
                            except json.JSONDecodeError:
                                continue
                except Exception as e:
                    _log_error("Error in message listener", e)
                    break
        except Exception as e:
            _log_error("Error in listener thread", e)
        finally:
            try:
                sock.close()
            except Exception as e:
                _log_error("Error closing socket", e)

    def _handle_server_message(self, msg: dict) -> None:
        """Handle incoming server messages."""
        logger.info(f"[AgentRunner] Received message from aco.server: {msg}")
        msg_type = msg.get("type")
        if msg_type == "restart":
            logger.info(f"[AgentRunner] Received restart message: {msg}")
            # In unified model, we exit gracefully and let server respawn us
            self.shutdown_flag = True
            sys.exit(0)
        elif msg_type == "shutdown":
            logger.info(f"[AgentRunner] Received shutdown message: {msg}")
            self.shutdown_flag = True
            sys.exit(0)

    def _is_debugpy_session(self) -> bool:
        """Detect if we're running under debugpy (VSCode debugging)."""
        try:
            return debugpy.is_client_connected() or hasattr(debugpy, "_client")
        except (ImportError, AttributeError):
            pass

        if "debugpy" in sys.modules:
            return True

        debugpy_env_vars = [
            "DEBUGPY_LAUNCHER_PORT",
            "PYDEVD_LOAD_VALUES_ASYNC",
            "PYDEVD_USE_FRAME_EVAL",
        ]
        return any(os.getenv(var) for var in debugpy_env_vars)

    def _get_parent_cmdline(self) -> List[str]:
        """Get the command line of the parent process."""
        try:
            current_process = psutil.Process()
            parent = current_process.parent()
            return parent.cmdline() if parent else []
        except Exception as e:
            _log_error("Failed to get parent cmdline", e)
            return []

    def _generate_restart_command(self) -> str:
        """Generate the appropriate command for restarting the script."""
        if not self._is_debugpy_session():
            return " ".join(sys.argv)

        python_executable = sys.executable
        parent_cmdline = self._get_parent_cmdline()

        # Handle debugpy launcher with -- separator
        if parent_cmdline and "launcher" in " ".join(parent_cmdline) and "--" in parent_cmdline:
            dash_index = parent_cmdline.index("--")
            original_args = " ".join(parent_cmdline[dash_index + 1 :])
            return f"/usr/bin/env {python_executable} {original_args}"

        # Generate target args based on module execution
        if self.is_module_execution:
            target_args = f"-m {self.script_path} {' '.join(self.script_args)}"
        else:
            target_args = f"{self.script_path} {' '.join(self.script_args)}"

        return f"{python_executable} {target_args}"

    def _connect_to_server(self) -> None:
        """Connect to the develop server and perform handshake."""
        try:
            self.server_conn = socket.create_connection((HOST, PORT), timeout=CONNECTION_TIMEOUT)
        except Exception as e:
            logger.error(f"Cannot connect to develop server: {e}")
            sys.exit(1)

        handshake = {
            "type": "hello",
            "role": "agent-runner",
            "name": "Workflow run",
            "cwd": os.getcwd(),
            "command": self._generate_restart_command(),
            "environment": dict(os.environ),
            "process_id": self.process_id,
            "prev_session_id": os.getenv("AGENT_COPILOT_SESSION_ID"),
            "module_to_file": MODULES_TO_FILES,
        }

        if self.user_id is not None:
            handshake["user_id"] = str(self.user_id)

        try:
            self.server_conn.sendall((json.dumps(handshake) + "\n").encode("utf-8"))
            file_obj = self.server_conn.makefile(mode="r")
            session_line = file_obj.readline()
            if session_line:
                session_msg = json.loads(session_line.strip())
                self.session_id = session_msg.get("session_id")
                database_mode = session_msg.get("database_mode")
                if database_mode:
                    DB.switch_mode(database_mode)
                    logger.debug(f"Using database mode: {database_mode}")
                logger.info(f"Registered with session_id: {self.session_id}")
        except Exception as e:
            _log_error("Server communication failed", e)
            raise

    def _setup_environment(self) -> None:
        """Set up the execution environment for the agent runner."""
        # Set up PYTHONPATH for AST rewrite hooks
        runtime_tracing_dir = get_runner_dir()

        if "PYTHONPATH" in os.environ:
            os.environ["PYTHONPATH"] = (
                self.project_root
                + os.pathsep
                + runtime_tracing_dir
                + os.pathsep
                + os.environ["PYTHONPATH"]
            )
        else:
            os.environ["PYTHONPATH"] = self.project_root + os.pathsep + runtime_tracing_dir

        # Set random seed
        if not os.environ.get("ACO_SEED"):
            os.environ["ACO_SEED"] = str(random.randint(0, 2**31 - 1))

        # Enable taint tracking in AST-rewritten code
        os.environ["AGENT_COPILOT_ENABLE_TRACING"] = "True"

        # Install AST hooks
        set_module_to_user_file(MODULES_TO_FILES)
        install_patch_hook()

        # Register taint functions in builtins
        builtins.taint_fstring_join = taint_fstring_join
        builtins.taint_format_string = taint_format_string
        builtins.taint_percent_format = taint_percent_format
        builtins.taint_open = taint_open
        builtins.exec_func = exec_func
        builtins.exec_setitem = exec_setitem
        builtins.exec_delitem = exec_delitem
        builtins.exec_inplace_binop = exec_inplace_binop
        builtins.wrap_assign = wrap_assign
        builtins.get_attr = get_attr
        builtins.get_item = get_item
        builtins.set_attr = set_attr
        builtins.wrap_if_needed = wrap_if_needed
        builtins.add_to_taint_dict_and_return = add_to_taint_dict_and_return
        builtins.get_taint = get_taint

        # Register ACTIVE_TAINT (ContextVar) for passing taint through third-party code
        builtins.ACTIVE_TAINT = ContextVar("active_taint", default=[])

        # Register TAINT_DICT (ThreadSafeWeakKeyDict) as single source of truth for taint
        from aco.runner.taint_dict import ThreadSafeWeakKeyDict

        builtins.TAINT_DICT = ThreadSafeWeakKeyDict()

    def _apply_runtime_setup(self) -> None:
        """Apply runtime setup for the agent runner execution environment."""
        # Set up context manager
        set_parent_session_id(self.session_id)
        set_server_connection(self.server_conn)

        # Apply monkey patches
        apply_all_monkey_patches()

        # Set random seeds
        aco_random_seed = int(os.environ["ACO_SEED"])
        random.seed(aco_random_seed)

        try:
            from numpy.random import seed

            seed(aco_random_seed)
        except ImportError:
            pass

        try:
            from torch import manual_seed

            manual_seed(aco_random_seed)
        except ImportError:
            pass

    def _convert_file_to_module_name(self, script_path: str) -> str:
        """Convert a file path to a module name that Python can import."""
        if os.path.isabs(script_path):
            abs_path = script_path
        else:
            abs_path = os.path.abspath(script_path)

        try:
            rel_path = os.path.relpath(abs_path, self.project_root)

            if rel_path.startswith(".."):
                module_name = os.path.splitext(os.path.basename(abs_path))[0]
                return module_name

            if rel_path.endswith(".py"):
                rel_path = rel_path[:-3]

            module_name = rel_path.replace(os.sep, ".")

            if module_name.endswith(".__init__"):
                module_name = module_name[:-9]

            if not module_name:
                module_name = os.path.splitext(os.path.basename(abs_path))[0]

            return module_name

        except ValueError:
            base_name = os.path.splitext(os.path.basename(abs_path))[0]
            return base_name

    def _execute_user_code(self) -> None:
        """Execute the user's code directly in this process."""
        try:
            # Ensure current working directory is in sys.path for module imports
            cwd = os.getcwd()
            if cwd not in sys.path:
                sys.path.insert(0, cwd)
                logger.info(f"[AgentRunner] Added current directory to sys.path: {cwd}")

            # Run user program.
            if self.is_module_execution:
                sys.argv = [self.script_path] + self.script_args
                runpy.run_module(self.script_path, run_name="__main__")
            else:
                module_name = self._convert_file_to_module_name(self.script_path)
                sys.argv = [self.script_path] + self.script_args
                runpy.run_module(module_name, run_name="__main__")
        except SystemExit as e:
            sys.exit(e.code if e.code is not None else 0)
        except Exception as e:
            _log_error("Error executing user code", e)
            sys.exit(1)

    def run(self) -> None:
        """Main entry point to run the unified agent runner."""
        try:
            self._setup_environment()
            ensure_server_running()
            self._connect_to_server()

            self.listener_thread = threading.Thread(
                target=self._listen_for_server_messages, args=(self.server_conn,), daemon=True
            )
            self.listener_thread.start()

            self._apply_runtime_setup()
            self._execute_user_code()

        finally:
            self.send_deregister()
            if self.server_conn:
                try:
                    self.server_conn.close()
                except Exception as e:
                    _log_error("Error closing server connection in cleanup", e)

            if self.listener_thread:
                self.listener_thread.join(timeout=2)
