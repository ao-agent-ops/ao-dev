import sys
import os
import socket
import json
import threading
import subprocess
import time
import signal
import select
import tempfile
import runpy
from typing import Optional, List
from runtime_tracing.fstring_rewriter import install_fstring_rewriter, set_user_py_files
from runtime_tracing.apply_monkey_patches import apply_all_monkey_patches
from common.logger import logger
from common.utils import get_project_root, scan_user_py_files_and_modules
from agent_copilot.launch_scripts import SCRIPT_WRAPPER_TEMPLATE, MODULE_WRAPPER_TEMPLATE


# Configuration constants
HOST = '127.0.0.1'
PORT = 5959
CONNECTION_TIMEOUT = 5
SERVER_START_TIMEOUT = 2
PROCESS_TERMINATE_TIMEOUT = 5
MESSAGE_POLL_INTERVAL = 0.1
SERVER_START_WAIT = 1

# Utility functions for path computation
def get_runtime_tracing_dir():
    """Return the absolute path to the runtime_tracing directory."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "runtime_tracing"))


class DevelopShim:
    """Manages the develop shim that runs user scripts with debugging support."""
    
    def __init__(self, script_path: str, script_args: List[str], is_module_execution: bool = False):
        self.script_path = script_path
        self.script_args = script_args
        self.is_module_execution = is_module_execution
        self.script_name = os.path.basename(script_path)
        self.role = "shim-control"
        
        # State management
        self.restart_event = threading.Event()
        self.shutdown_flag = False
        self.socket_closed = False
        self.proc: Optional[subprocess.Popen] = None
        self.wrapper_path: Optional[str] = None
        
        # Server communication
        self.session_id: Optional[str] = None
        self.server_conn: Optional[socket.socket] = None
        
        # Threading
        self.listener_thread: Optional[threading.Thread] = None
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _send_message(self, msg_type: str, **kwargs) -> None:
        """Send a message to the develop server."""
        if not self.server_conn:
            return
        message = {
            "type": msg_type,
            "role": self.role,
            "script": self.script_name,
            **kwargs
        }
        if self.session_id:
            message["session_id"] = self.session_id
        try:
            self.server_conn.sendall((json.dumps(message) + "\n").encode('utf-8'))
        except Exception:
            pass  # Best effort only
    
    def send_deregister(self) -> None:
        """Send deregistration message to the develop server."""
        self._send_message("deregister")
    
    def send_restart_notification(self) -> None:
        """Send restart notification to the develop server."""
        self._send_message("debugger_restart")
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle termination signals gracefully."""
        self.send_deregister()
        if self.server_conn:
            try:
                self.server_conn.close()
            except Exception:
                pass
        sys.exit(0)
    
    def _listen_for_server_messages(self, sock: socket.socket) -> None:
        """Background thread: listen for 'restart' or 'shutdown' messages from the server."""
        try:
            sock.setblocking(False)
            buffer = b''
            while not self.shutdown_flag and not self.socket_closed:
                try:
                    rlist, _, _ = select.select([sock], [], [], 1.0)
                    if rlist:
                        try:
                            data = sock.recv(4096)
                            if not data:
                                break  # Socket closed
                            buffer += data
                            while b'\n' in buffer:
                                line, buffer = buffer.split(b'\n', 1)
                                try:
                                    msg = json.loads(line.decode('utf-8').strip())
                                except json.JSONDecodeError:
                                    continue
                                self._handle_server_message(msg)
                        except Exception:
                            break  # Any error, exit thread
                except Exception:
                    break
        except Exception:
            pass
        finally:
            try:
                sock.close()
            except Exception:
                pass
    
    def _handle_server_message(self, msg: dict) -> None:
        """Handle incoming server messages."""
        logger.info(f"[shim-control] Received message from server: {msg}")
        msg_type = msg.get("type")
        if msg_type == "restart":
            logger.info(f"[shim-control] Received restart message: {msg}")
            self.restart_event.set()
        elif msg_type == "shutdown":
            logger.info(f"[shim-control] Received shutdown message: {msg}")
            self.shutdown_flag = True
    
    def _setup_monkey_patching_env(self) -> dict:
        """Set up environment variables to enable monkey patching in the user's script."""
        env = os.environ.copy()
        
        # Add the runtime_tracing directory to PYTHONPATH so sitecustomize.py can be found
        runtime_tracing_dir = get_runtime_tracing_dir()
        
        # Load project_root from copilot.yaml
        project_root = get_project_root()
        
        # Add to PYTHONPATH: project_root first, then runtime_tracing_dir
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = project_root + os.pathsep + runtime_tracing_dir + os.pathsep + env['PYTHONPATH']
        else:
            env['PYTHONPATH'] = project_root + os.pathsep + runtime_tracing_dir
        
        # Set environment variables to enable monkey patching
        env['AGENT_COPILOT_ENABLE_TRACING'] = '1'
        env['AGENT_COPILOT_SERVER_HOST'] = HOST
        env['AGENT_COPILOT_SERVER_PORT'] = str(PORT)
        
        # Pass the session id to the child process
        if self.session_id:
            env['AGENT_COPILOT_SESSION_ID'] = self.session_id
        
        return env
    
    def _ensure_server_running(self) -> None:
        """Ensure the develop server is running, start it if necessary."""
        try:
            socket.create_connection((HOST, PORT), timeout=SERVER_START_TIMEOUT).close()
        except Exception:
            server_py = os.path.join(os.path.dirname(__file__), "develop_server.py")
            try:
                subprocess.Popen([sys.executable, server_py, "start"])
            except Exception as e:
                logger.error(f"Failed to start develop server ({e})")
                sys.exit(1)
            time.sleep(SERVER_START_WAIT)
            try:
                socket.create_connection((HOST, PORT), timeout=CONNECTION_TIMEOUT).close()
            except Exception:
                logger.error("Develop server did not start.")
                sys.exit(1)
    
    def _connect_to_server(self) -> None:
        """Connect to the develop server and perform handshake."""
        try:
            self.server_conn = socket.create_connection((HOST, PORT), timeout=CONNECTION_TIMEOUT)
        except Exception as e:
            logger.error(f"Cannot connect to develop server ({e})")
            sys.exit(1)
        # Send handshake to server
        handshake = {
            "type": "hello",
            "role": self.role,
            "script": self.script_name,
            "cwd": os.getcwd(),
            "command": " ".join(sys.argv)
        }
        try:
            self.server_conn.sendall((json.dumps(handshake) + "\n").encode('utf-8'))
            # Read session_id from server
            file_obj = self.server_conn.makefile(mode='r')
            session_line = file_obj.readline()
            if session_line:
                try:
                    session_msg = json.loads(session_line.strip())
                    self.session_id = session_msg.get("session_id")
                    logger.info(f"[shim-control] Registered with session_id: {self.session_id}")
                except Exception:
                    pass
        except Exception:
            pass
    
    def _convert_and_run_as_module(self, script_path: str, script_args: List[str]) -> Optional[int]:
        """Convert script execution to module import for AST rewriting."""
        abs_path = os.path.abspath(script_path)
        script_dir = os.path.dirname(abs_path)
        
        # Set up file scanning and mapping in current process
        
        # Load project_root from copilot.yaml
        project_root = get_project_root()
        
        # Scan for all .py files in the user's project root
        # This ensures AST rewriting works for the user's code
        user_py_files, file_to_module = scan_user_py_files_and_modules(project_root)
        set_user_py_files(user_py_files, file_to_module)
        install_fstring_rewriter()
        
        # Apply monkey patches in the current process
        apply_all_monkey_patches(self.server_conn)
        
        # Save original state
        original_path = sys.path.copy()
        original_argv = sys.argv.copy()
        
        try:
            # Add project root to sys.path for module import
            sys.path.insert(0, project_root)
            
            # Set up argv for the script
            sys.argv = [script_path] + script_args
            
            # Compute module name as absolute path from project root
            # TODO: Assumes the project is installed with pip install -e, we can use absolute module names
            rel_path = os.path.relpath(abs_path, project_root)
            if rel_path.startswith('..'):
                # If the file is outside the project root, use the filename as module name
                module_name = os.path.splitext(os.path.basename(abs_path))[0]
            else:
                # Convert relative path to module name
                module_name = rel_path[:-3].replace(os.sep, '.')  # strip .py, convert / to .
            
            # Import and run as module (this triggers AST rewriting)
            runpy.run_module(module_name, run_name='__main__')
            return 0
        except SystemExit as e:
            return e.code if e.code is not None else 0
        except Exception as e:
            logger.error(f"Error running script as module: {e}")
            return 1
        finally:
            # Restore original state
            sys.path[:] = original_path
            sys.argv[:] = original_argv

    def _convert_file_to_module_name(self, script_path: str) -> str:
        """Convert a file path to a module name that Python can import."""
        # Handle absolute paths
        if os.path.isabs(script_path):
            abs_path = script_path
        else:
            abs_path = os.path.abspath(script_path)
                
        # Load project_root from copilot.yaml
        project_root = get_project_root()
                
        # Compute module name, handling files outside the project root
        try:
            rel_path = os.path.relpath(abs_path, project_root)
            
            if rel_path.startswith('..'):
                # If the file is outside the project root, use the filename as module name
                module_name = os.path.splitext(os.path.basename(abs_path))[0]
                return module_name
            
            # Remove .py extension
            if rel_path.endswith('.py'):
                rel_path = rel_path[:-3]
            
            # Convert path separators to dots
            module_name = rel_path.replace(os.sep, '.')
            
            # Handle __init__.py files (remove .__init__ suffix)
            if module_name.endswith('.__init__'):
                module_name = module_name[:-9]
            
            # Handle empty module names (file is at project root)
            if not module_name:
                module_name = os.path.splitext(os.path.basename(abs_path))[0]
            
            return module_name
            
        except ValueError as e:
            # If the file is not relative to the project root, use filename
            base_name = os.path.splitext(os.path.basename(abs_path))[0]
            return base_name

    def _create_runpy_wrapper(self, module_name: str, script_args: List[str], project_root: str) -> str:
        """
        Create a temporary wrapper script that runs the module with runpy.run_module.
        This is needed for script execution (develop script.py) so that AST patching and import hooks
        are applied to the main script, which would not happen if run directly as __main__.
        """
        runtime_tracing_dir = get_runtime_tracing_dir()
        wrapper_code = SCRIPT_WRAPPER_TEMPLATE.format(
            runtime_tracing_dir=runtime_tracing_dir,
            project_root=project_root,
            module_name=repr(module_name),
            script_args=repr(script_args)
        )
        fd, temp_path = tempfile.mkstemp(suffix='.py', prefix='develop_runpy_wrapper_')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(wrapper_code)
        return temp_path

    def _run_user_script_subprocess(self) -> Optional[int]:
        """
        Run the user's script as a subprocess with proper environment setup.
        This method handles both module and script execution, generating a wrapper script as needed
        to ensure AST patching and import hooks are applied to all user code.
        """
        env = self._setup_monkey_patching_env()
        project_root = get_project_root()
        if self.is_module_execution:
            # For module execution, create a wrapper that sets up AST rewriting and resolves module names
            runtime_tracing_dir = get_runtime_tracing_dir()
            wrapper_code = MODULE_WRAPPER_TEMPLATE.format(
                runtime_tracing_dir=runtime_tracing_dir,
                project_root=project_root,
                module_name=repr(self.script_path),
                script_args=repr(self.script_args)
            )
            fd, temp_path = tempfile.mkstemp(suffix='.py', prefix='develop_module_wrapper_')
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(wrapper_code)
            self.proc = subprocess.Popen([sys.executable, temp_path], env=env)
            self.wrapper_path = temp_path
        else:
            # For file execution, convert to module name and use wrapper
            module_name = self._convert_file_to_module_name(self.script_path)
            wrapper_path = self._create_runpy_wrapper(module_name, self.script_args, project_root)
            self.proc = subprocess.Popen([sys.executable, wrapper_path], env=env)
            self.wrapper_path = wrapper_path
        # Monitor the process and check for restart requests
        try:
            while self.proc.poll() is None:
                if self.restart_event.is_set():
                    logger.info("[shim-control] Restart event detected. Terminating user process.")
                    self.proc.terminate()
                    try:
                        self.proc.wait(timeout=PROCESS_TERMINATE_TIMEOUT)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                        self.proc.wait()
                    logger.info("[shim-control] User process terminated. Will restart.")
                    return None
                time.sleep(MESSAGE_POLL_INTERVAL)
            self.proc.wait()
        except KeyboardInterrupt:
            self.proc.terminate()
            self.proc.wait()
        finally:
            # Clean up wrapper file
            if self.wrapper_path:
                try:
                    os.unlink(self.wrapper_path)
                    self.wrapper_path = None
                except Exception:
                    pass
        return self.proc.returncode
    
    def _run_user_script_debug_mode(self) -> int:
        """Run the user's script in debug mode with restart detection."""
        import importlib.util
        
        # Load the script as a module
        spec = importlib.util.spec_from_file_location("user_script", self.script_path)
        module = importlib.util.module_from_spec(spec)
        
        # Add script args to sys.argv for the script
        original_argv = sys.argv.copy()
        sys.argv = [self.script_path] + self.script_args
        
        try:
            # Execute the script
            spec.loader.exec_module(module)
        finally:
            # Restore original argv
            sys.argv = original_argv
    
    def _kill_current_process(self) -> None:
        """Kill the current subprocess if it's still running."""
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=PROCESS_TERMINATE_TIMEOUT)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            except Exception:
                pass
    
    def _is_debug_mode(self) -> bool:
        """Check if we're running in debug mode."""
        try:
            import debugpy
            return debugpy.is_client_connected()
        except Exception:
            return False
    
    def _run_debug_mode(self) -> None:
        """Run the script in debug mode."""
        logger.info("Debug mode detected. Running script in debug context.")
        logger.info("Running script in debug mode...")
        
        returncode = self._run_user_script_debug_mode()
        
        # If restart was requested during execution, handle it
        if returncode is None:
            logger.info("Restart requested during execution, restarting script...")
            self.restart_event.clear()
            # Run the script again
            self._run_user_script_debug_mode()
    
    def _run_normal_mode(self) -> None:
        """Run the script in normal mode with restart handling."""
        while not self.shutdown_flag:
            logger.info("[shim-control] Starting user script subprocess.")
            returncode = self._run_user_script_subprocess()
            if self.shutdown_flag:
                break
            # Check if restart was requested during execution
            if returncode is None:
                logger.info("[shim-control] Restart requested, restarting script...")
                self.restart_event.clear()
                continue
            # Check if restart was requested after completion
            if returncode is not None and self.restart_event.is_set():
                logger.info("[shim-control] Restart requested, restarting script...")
                self.restart_event.clear()
                continue
            # No restart requested, exit
            break
    
    def run(self) -> None:
        """Main entry point to run the develop shim."""
        # Ensure server is running and connect to it
        self._ensure_server_running()
        self._connect_to_server()
        
        # Start background thread to listen for server messages
        self.listener_thread = threading.Thread(
            target=self._listen_for_server_messages, 
            args=(self.server_conn,)
        )
        self.listener_thread.start()

        try:
            if self._is_debug_mode():
                self._run_debug_mode()
            else:
                self._run_normal_mode()
        finally:
            # Kill any remaining subprocess before cleanup
            self._kill_current_process()
            
            # Clean up
            self.send_deregister()
            if self.server_conn:
                try:
                    self.socket_closed = True  # Signal background thread to exit
                    self.server_conn.close()
                except Exception:
                    pass
            
            # Wait for background thread to finish
            if self.listener_thread:
                self.listener_thread.join(timeout=2)
        
        sys.exit(0)

def main():
    """Entry point for the develop command."""
    if len(sys.argv) < 2:
        logger.error("Usage: develop <script.py> [script args...] or develop -m <module> [module args...]")
        sys.exit(1)
    
    # Check if user is running as module (-m flag)
    is_module_execution = False
    if sys.argv[1] == '-m':
        if len(sys.argv) < 3:
            logger.error("No module specified after -m")
            logger.error("Usage: develop -m <module> [module args...]")
            sys.exit(1)
        # Module execution: pass through to subprocess
        script_path = sys.argv[2]  # This will be the module name
        script_args = sys.argv[3:]
        is_module_execution = True
    else:
        # Direct execution: convert to module import
        script_path = sys.argv[1]
        script_args = sys.argv[2:]
    
    shim = DevelopShim(script_path, script_args, is_module_execution)
    shim.run()

if __name__ == "__main__":
    main()
