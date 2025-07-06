import socket
import sys
import os
import argparse
import json
import threading
import subprocess
import select
import uuid
import time
from typing import Dict, Any, Optional, Set

# Configuration constants
HOST = '127.0.0.1'
PORT = 5959
SOCKET_TIMEOUT = 3
SHUTDOWN_WAIT = 2

class Session:
    """Represents a running develop process and its associated UI clients."""
    
    def __init__(self, session_id: str, script_name: str):
        self.session_id = session_id
        self.script_name = script_name
        self.shim_conn: Optional[socket.socket] = None
        self.ui_conns: Set[socket.socket] = set()
        self.lock = threading.Lock()  # To protect concurrent access

class DevelopServer:
    """Manages the development server for LLM call visualization."""
    
    def __init__(self):
        # Global state for tracking connected clients and LLM call records
        self.clients = {
            "shim_control": [],  # shim controller connections (orchestrators)
            "shim_runner": [],   # shim runner connections (sending call data)
            "extension": []      # extension client connections
        }
        self.calls = []              # list of recorded LLM call details (with assigned IDs)
        self.call_id_counter = 1     # incremental ID generator for calls
        
        # Add global mapping for shim process IDs
        self.dashim_pid_map: Dict[int, tuple] = {}  # process_id -> (session_id, shim_conn)
        
        # Map session_id to Session
        self.sessions: Dict[str, Session] = {}
        
        # Map socket to (role, session_id)
        self.conn_info: Dict[socket.socket, Dict[str, Any]] = {}
        
        # Server socket
        self.server_sock: Optional[socket.socket] = None
    
    def send_json(self, conn: socket.socket, msg: dict) -> None:
        """Send a JSON message to a client."""
        try:
            conn.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        except Exception:
            pass  # Best effort only
    
    def broadcast_to_uis(self, session: Session, msg: dict) -> None:
        """Broadcast a message to all UI connections in a session."""
        for ui_conn in list(session.ui_conns):
            try:
                self.send_json(ui_conn, msg)
            except Exception:
                session.ui_conns.discard(ui_conn)
    
    def route_message(self, sender: socket.socket, msg: dict) -> None:
        """Route a message based on sender role."""
        info = self.conn_info.get(sender)
        if not info:
            return
        role = info["role"]
        session_id = info["session_id"]
        session = self.sessions.get(session_id)
        if not session:
            return
        
        # Route based on sender role
        if role == "ui":
            # UI → Shim
            if session.shim_conn:
                self.send_json(session.shim_conn, msg)
        elif role == "shim":
            # Shim → all UIs
            # TODO: I think we don't need to send to all uis, only the relevant one.
            self.broadcast_to_uis(session, msg)
    
    def user_edit(self, llm_call_id: int, new_input: str) -> None:
        """
        Handle a user edit request by instructing the shim to restart the user process.
        In practice, the VS Code extension would call this (e.g. via a socket message),
        and it sends a restart signal to the shim along with the edited input.
        """
        message = {"type": "restart", "id": llm_call_id, "new_input": new_input}
        data = (json.dumps(message) + "\n").encode('utf-8')
        # Send the restart instruction to all connected shim controllers
        with threading.Lock():  # ensure thread-safe sending
            for conn in list(self.clients.get("shim_control", [])):
                print("send to shim")
                try:
                    conn.sendall(data)
                except Exception:
                    # Remove disconnected clients
                    self.clients["shim_control"].remove(conn)
    
    def handle_shutdown(self) -> None:
        """Handle shutdown command by closing all connections."""
        print("[develop_server] Shutdown command received. Closing all connections.")
        # Close all client sockets
        for s in list(self.conn_info.keys()):
            print(f"Closing socket: {s}")
            try:
                s.close()
            except Exception as e:
                print(f"Error closing socket: {e}")
        os._exit(0)
    
    def handle_restart_message(self, msg: dict) -> bool:
        """Handle restart message with process_id, route to correct shim."""
        if msg.get("type") == "restart" and "process_id" in msg:
            pid = msg["process_id"]
            target = self.dashim_pid_map.get(pid)
            if target:
                _, shim_conn = target
                self.send_json(shim_conn, msg)
                return True  # Message handled
        return False
    
    def handle_deregister_message(self, msg: dict) -> bool:
        """Handle deregister message, remove from pid map and broadcast."""
        if msg.get("type") == "deregister" and "process_id" in msg:
            pid = msg["process_id"]
            if pid in self.dashim_pid_map:
                del self.dashim_pid_map[pid]
                # Broadcast updated shim list to all UIs
                for sess in self.sessions.values():
                    for ui_conn in list(sess.ui_conns):
                        self.send_json(ui_conn, {"type": "shim_list", "pids": list(self.dashim_pid_map.keys())})
                return True  # Message handled
        return False
    
    def handle_debugger_restart_message(self, msg: dict) -> bool:
        """Handle debugger restart notification, update session info."""
        if msg.get("type") == "debugger_restart" and "process_id" in msg:
            pid = msg["process_id"]
            script_name = msg.get("script", "unknown")
            print(f"[develop_server] Debugger restart detected for PID {pid}, script: {script_name}")
            # Update the session info to reflect the restart
            if pid in self.dashim_pid_map:
                session_id, shim_conn = self.dashim_pid_map[pid]
                if session_id in self.sessions:
                    self.sessions[session_id].script_name = script_name
                    # Broadcast updated session info to UIs
                    for sess in self.sessions.values():
                        for ui_conn in list(sess.ui_conns):
                            self.send_json(ui_conn, {
                                "type": "session_restart", 
                                "process_id": pid,
                                "script": script_name
                            })
            return True  # Message handled
        return False
    
    def handle_client(self, conn: socket.socket, addr) -> None:
        """Handle a new client connection in a separate thread."""
        print(f"New client connection from {addr}")
        file_obj = conn.makefile(mode='r')
        session: Optional[Session] = None
        process_id = None
        
        try:
            # Expect handshake first
            handshake_line = file_obj.readline()
            if not handshake_line:
                return
            handshake = json.loads(handshake_line.strip())
            role = handshake.get("role")
            script = handshake.get("script")
            session_id = handshake.get("session_id")
            process_id = handshake.get("process_id")
            
            if not session_id:
                session_id = str(uuid.uuid4())
            
            with threading.Lock():
                if session_id not in self.sessions:
                    self.sessions[session_id] = Session(session_id, script or "")
                session = self.sessions[session_id]
            
            if role == "shim-runner" or role == "shim-control":
                with session.lock:
                    session.shim_conn = conn
                if process_id is not None:
                    self.dashim_pid_map[process_id] = (session_id, conn)
                    # Broadcast updated shim list to all UIs
                    for sess in self.sessions.values():
                        for ui_conn in list(sess.ui_conns):
                            self.send_json(ui_conn, {"type": "shim_list", "pids": list(self.dashim_pid_map.keys())})
            elif role == "ui":
                with session.lock:
                    session.ui_conns.add(conn)
                # On UI connect, send list of shim pids
                shim_pids = list(self.dashim_pid_map.keys())
                self.send_json(conn, {"type": "shim_list", "pids": shim_pids})
            
            self.conn_info[conn] = {"role": role, "session_id": session_id, "process_id": process_id}
            self.send_json(conn, {"type": "session_id", "session_id": session_id, "script": session.script_name})
            
            # Main message loop
            try:
                for line in file_obj:
                    print(f"[develop_server] Raw line received: {line!r}")
                    try:
                        msg = json.loads(line.strip())
                    except Exception:
                        continue
                    
                    if "session_id" not in msg:
                        msg["session_id"] = session_id
                    
                    # Print when a 'restart' message is received (for verification)
                    if msg.get("type") == "restart":
                        print(f"[develop_server] Received restart message: {msg}")
                    
                    # Handle special message types
                    if msg.get("type") == "shutdown":
                        self.handle_shutdown()
                    elif self.handle_restart_message(msg):
                        continue  # Don't route to all shims
                    elif self.handle_deregister_message(msg):
                        continue
                    elif self.handle_debugger_restart_message(msg):
                        continue
                    else:
                        self.route_message(conn, msg)
                        
            except (ConnectionResetError, OSError):
                # Socket closed, exit thread quietly
                pass
        finally:
            # Clean up connection
            info = self.conn_info.pop(conn, None)
            if info and session:
                if info["role"] == "shim":
                    with session.lock:
                        session.shim_conn = None
                    # Remove from pid map if present
                    for pid, (sess_id, c) in list(self.dashim_pid_map.items()):
                        if c == conn:
                            del self.dashim_pid_map[pid]
                elif info["role"] == "ui":
                    with session.lock:
                        session.ui_conns.discard(conn)
            try:
                conn.close()
            except Exception:
                pass
    
    def run_server(self) -> None:
        """Main server loop: accept clients and spawn handler threads."""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((HOST, PORT))
        self.server_sock.listen()
        print(f"Develop server listening on {HOST}:{PORT}")
        
        try:
            while True:
                conn, addr = self.server_sock.accept()
                threading.Thread(
                    target=self.handle_client, 
                    args=(conn, addr), 
                    daemon=True
                ).start()
        except OSError:
            # This will be triggered when server_sock is closed (on shutdown)
            pass
        finally:
            self.server_sock.close()
            print("Develop server stopped.")

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Development server for LLM call visualization")
    parser.add_argument('command', choices=['start', 'stop', 'edit', 'restart'], 
                       help="Start or stop the server")
    args = parser.parse_args()

    if args.command == 'start':
        # If server is already running, do not start another
        try:
            socket.create_connection((HOST, PORT), timeout=1).close()
            print("Develop server is already running.")
            return
        except Exception:
            pass
        # Launch the server as a detached background process (POSIX)
        subprocess.Popen([sys.executable, __file__, "--serve"],
                        close_fds=True, start_new_session=True)
        print("Develop server started.")
        
    elif args.command == 'stop':
        # Connect to the server and send a shutdown command
        try:
            sock = socket.create_connection((HOST, PORT), timeout=SOCKET_TIMEOUT)
            # The server will only accept messages from this process after a handshake.
            handshake = {"type": "hello", "role": "ui", "script": "stopper"}
            sock.sendall((json.dumps(handshake) + "\n").encode('utf-8'))
            # Send shutdown message
            sock.sendall((json.dumps({"type": "shutdown"}) + "\n").encode('utf-8'))
            sock.close()
            print("Develop server stop signal sent.")
        except Exception:
            print("No running server found.")
            sys.exit(1)
            
    elif args.command == 'restart':
        # Stop the server if running
        try:
            sock = socket.create_connection((HOST, PORT), timeout=SOCKET_TIMEOUT)
            handshake = {"type": "hello", "role": "ui", "script": "restarter"}
            sock.sendall((json.dumps(handshake) + "\n").encode('utf-8'))
            sock.sendall((json.dumps({"type": "shutdown"}) + "\n").encode('utf-8'))
            sock.close()
            print("Develop server stop signal sent (for restart). Waiting for shutdown...")
            time.sleep(SHUTDOWN_WAIT)
        except Exception:
            print("No running server found. Proceeding to start.")
        # Start the server
        subprocess.Popen([sys.executable, __file__, "--serve"],
                        close_fds=True, start_new_session=True)
        print("Develop server restarted.")
        
    elif args.command == '--serve':
        # Internal: run the server loop (not meant to be called by users directly)
        server = DevelopServer()
        server.run_server()

    # DEBUG: Call from VS Code extension in the future.
    elif args.command == 'edit':
        server = DevelopServer()
        server.user_edit(llm_call_id=42, new_input="hello 42")

if __name__ == "__main__":
    # Support internal "--serve" invocation to actually run the server loop
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        server = DevelopServer()
        server.run_server()
    else:
        print(f"[develop_server] Starting server on {HOST}:{PORT}, PID={os.getpid()}")
        main()
