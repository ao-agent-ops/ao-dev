import sys
import os
import socket
import json
import threading
import subprocess
import time
import signal
import select
from typing import Optional, List

# Configuration constants
HOST = '127.0.0.1'
PORT = 5959
CONNECTION_TIMEOUT = 5
SERVER_START_TIMEOUT = 2
PROCESS_TERMINATE_TIMEOUT = 5
MESSAGE_POLL_INTERVAL = 0.1
SERVER_START_WAIT = 1

class DevelopShim:
    """Manages the development shim that runs user scripts with debugging support."""
    
    def __init__(self, script_path: str, script_args: List[str]):
        self.script_path = script_path
        self.script_args = script_args
        self.script_name = os.path.basename(script_path)
        self.role = "shim-control"
        
        # State management
        self.restart_event = threading.Event()
        self.shutdown_flag = False
        self.socket_closed = False
        self.proc: Optional[subprocess.Popen] = None
        
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
            "process_id": os.getpid(),
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
        msg_type = msg.get("type")
        if msg_type == "restart":
            print(f"[DEBUG] Received restart message: {msg}")
            self.restart_event.set()
        elif msg_type == "shutdown":
            print(f"[DEBUG] Received shutdown message: {msg}")
            self.shutdown_flag = True
    
    def _setup_monkey_patching_env(self) -> dict:
        """Set up environment variables to enable monkey patching in the user's script."""
        env = os.environ.copy()
        
        # Add the runtime_tracing directory to PYTHONPATH so sitecustomize.py can be found
        runtime_tracing_dir = os.path.join(os.path.dirname(__file__), "..", "runtime_tracing")
        runtime_tracing_dir = os.path.abspath(runtime_tracing_dir)
        
        # Add to PYTHONPATH
        if 'PYTHONPATH' in env:
            env['PYTHONPATH'] = runtime_tracing_dir + os.pathsep + env['PYTHONPATH']
        else:
            env['PYTHONPATH'] = runtime_tracing_dir
        
        # Set environment variables to enable monkey patching
        env['AGENT_COPILOT_ENABLE_TRACING'] = '1'
        env['AGENT_COPILOT_SERVER_HOST'] = HOST
        env['AGENT_COPILOT_SERVER_PORT'] = str(PORT)
        
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
                print(f"Error: Failed to start develop server ({e})")
                sys.exit(1)
            time.sleep(SERVER_START_WAIT)
            try:
                socket.create_connection((HOST, PORT), timeout=CONNECTION_TIMEOUT).close()
            except Exception:
                print("Error: Develop server did not start.")
                sys.exit(1)
    
    def _connect_to_server(self) -> None:
        """Connect to the develop server and perform handshake."""
        try:
            self.server_conn = socket.create_connection((HOST, PORT), timeout=CONNECTION_TIMEOUT)
        except Exception as e:
            print(f"Error: Cannot connect to develop server ({e})")
            sys.exit(1)
        
        # Send handshake to server
        handshake = {
            "type": "hello", 
            "role": self.role, 
            "script": self.script_name, 
            "process_id": os.getpid()
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
                except Exception:
                    pass
        except Exception:
            pass
    
    def _run_user_script_subprocess(self) -> Optional[int]:
        """Run the user's script as a subprocess with proper environment setup."""
        env = self._setup_monkey_patching_env()
        self.proc = subprocess.Popen([sys.executable, self.script_path] + self.script_args, env=env)
        try:
            # Monitor the process and check for restart requests
            while self.proc.poll() is None:
                if self.restart_event.is_set():
                    # Restart requested, kill the current process
                    self.proc.terminate()
                    try:
                        self.proc.wait(timeout=PROCESS_TERMINATE_TIMEOUT)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                        self.proc.wait()
                    return None  # Signal that restart was requested
                time.sleep(MESSAGE_POLL_INTERVAL)
            self.proc.wait()
        except KeyboardInterrupt:
            self.proc.terminate()
            self.proc.wait()
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
            return 0
        except SystemExit as e:
            return e.code if e.code is not None else 0
        except Exception as e:
            print(f"Error running script: {e}")
            return 1
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
        print("Debug mode detected. Running script in debug context.")
        print("Running script in debug mode...")
        
        returncode = self._run_user_script_debug_mode()
        
        # If restart was requested during execution, handle it
        if returncode is None:
            print("Restart requested during execution, restarting script...")
            self.restart_event.clear()
            # Run the script again
            self._run_user_script_debug_mode()
    
    def _run_normal_mode(self) -> None:
        """Run the script in normal mode with restart handling."""
        while not self.shutdown_flag:
            returncode = self._run_user_script_subprocess()
            
            if self.shutdown_flag:
                break
            
            # Check if restart was requested during execution
            if returncode is None:
                print("Restart requested, restarting script...")
                self.restart_event.clear()
                continue
            
            # Check if restart was requested after completion
            if returncode is not None and self.restart_event.is_set():
                print("Restart requested, restarting script...")
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
        print("Usage: develop <script.py> [script args...]")
        sys.exit(1)
    
    script_path = sys.argv[1]
    script_args = sys.argv[2:]
    
    shim = DevelopShim(script_path, script_args)
    shim.run()

if __name__ == "__main__":
    main()
