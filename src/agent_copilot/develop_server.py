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
import copy
from datetime import datetime
from typing import Dict, Any, Optional, Set, Tuple

# Configuration constants
HOST = '127.0.0.1'
PORT = 5959
SOCKET_TIMEOUT = 3
SHUTDOWN_WAIT = 2

EXAMPLE_GRAPH = {
    "nodes": [
        {"id": "1", "input": "User input data", "output": "Processed user data", "codeLocation": "file.py:15", "label": "User Input Handler", "border_color": "#ff3232"},
        {"id": "2", "input": "Processed user data", "output": "Validated data", "codeLocation": "file.py:42", "label": "Data Validator", "border_color": "#00c542"},
        {"id": "3", "input": "Validated data", "output": "Database query", "codeLocation": "file.py:78", "label": "Query Builder", "border_color": "#ffba0c"},
        {"id": "4", "input": "Database query", "output": "Query results", "codeLocation": "file.py:23", "label": "Query Executor", "border_color": "#ffba0c"},
        {"id": "5", "input": "Query results", "output": "Formatted response", "codeLocation": "file.py:56", "label": "Response Formatter", "border_color": "#00c542"},
        {"id": "6", "input": "Validated data", "output": "Cache key", "codeLocation": "file.py:12", "label": "Cache Key Generator", "border_color": "#ff3232"},
        {"id": "7", "input": "Cache key", "output": "Cache status", "codeLocation": "file.py:34", "label": "Cache Manager", "border_color": "#00c542"}
    ],
    "edges": [
        {"id": "e1-2", "source": "1", "target": "2"},
        {"id": "e2-3", "source": "2", "target": "3"},
        {"id": "e3-4", "source": "3", "target": "4"},
        {"id": "e4-5", "source": "4", "target": "5"},
        {"id": "e2-6", "source": "2", "target": "6"},
        {"id": "e6-7", "source": "6", "target": "7"},
        {"id": "e7-5", "source": "7", "target": "5"}
    ]
}

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
        self.clients: Dict[str, list] = {
            "shim_control": [],
            "shim_runner": [],
            "extension": []
        }
        self.calls: list = []
        self.call_id_counter: int = 1
        self.dashim_pid_map: Dict[int, Tuple[str, socket.socket]] = {}
        self.sessions: Dict[str, Session] = {}
        self.conn_info: Dict[socket.socket, Dict[str, Any]] = {}
        self.process_info: Dict[int, Dict[str, Any]] = {}
        self.server_sock: Optional[socket.socket] = None
        self.lock = threading.Lock()
    
    def send_json(self, conn: socket.socket, msg: dict) -> None:
        try:
            conn.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        except Exception as e:
            print(f"[develop_server] Error sending JSON: {e}")
    
    def broadcast_to_uis(self, session: Session, msg: dict) -> None:
        """Broadcast a message to all UI connections in a session."""
        for ui_conn in list(session.ui_conns):
            try:
                self.send_json(ui_conn, msg)
            except Exception:
                session.ui_conns.discard(ui_conn)
    
    def broadcast_process_list_to_all_uis(self) -> None:
        process_list = [
            {
                "pid": pid,
                "script_name": info.get("script_name", "unknown"),
                "session_id": info.get("session_id", ""),
                "status": info.get("status", "running"),
                "role": info.get("role", "shim-control"),
                "graph": info.get("graph"),
                "timestamp": info.get("timestamp", "")
            }
            for pid, info in self.process_info.items() if info.get("role") == "shim-control"
        ]
        msg = {"type": "process_list", "processes": process_list}
        for session in self.sessions.values():
            for ui_conn in list(session.ui_conns):
                try:
                    self.send_json(ui_conn, msg)
                except Exception as e:
                    print(f"[develop_server] Error broadcasting to UI: {e}")
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
        if msg.get("type") == "deregister" and "process_id" in msg:
            pid = msg["process_id"]
            role = None
            for conn, info in list(self.conn_info.items()):
                if info.get("process_id") == pid:
                    role = info.get("role")
                    break
            if pid in self.dashim_pid_map:
                del self.dashim_pid_map[pid]
                self._mark_process_finished(role, pid)
                return True
        return False
    
    def handle_debugger_restart_message(self, msg: dict) -> bool:
        """Handle debugger restart notification, update session info."""
        if msg.get("type") == "debugger_restart" and "process_id" in msg:
            pid = msg["process_id"]
            script_name = msg.get("script", "unknown")
            print(f"[develop_server] Debugger restart detected for PID {pid}, script: {script_name}")
            if pid in self.dashim_pid_map:
                session_id, shim_conn = self.dashim_pid_map[pid]
                if session_id in self.sessions:
                    self.sessions[session_id].script_name = script_name
                    if pid in self.process_info:
                        self.process_info[pid]["script_name"] = script_name
                        self.broadcast_process_list_to_all_uis()
            return True
        return False
    
    def _track_process(self, role: str, process_id: int, script: str, session_id: str) -> None:
        if role == "shim-control":
            # Create timestamp in DD/MM HH:MM format
            timestamp = datetime.now().strftime("%d/%m %H:%M")
            self.process_info[process_id] = {
                "script_name": script or "unknown",
                "session_id": session_id,
                "status": "running",
                "role": role,
                "graph": copy.deepcopy(EXAMPLE_GRAPH),
                "timestamp": timestamp
            }
            self.broadcast_process_list_to_all_uis()

    def _mark_process_finished(self, role: str, process_id: int) -> None:
        if role == "shim-control" and process_id in self.process_info:
            self.process_info[process_id]["status"] = "finished"
            self.broadcast_process_list_to_all_uis()
    
    def handle_client(self, conn: socket.socket, addr) -> None:
        """Handle a new client connection in a separate thread."""
        print(f"New client connection from {addr}")
        file_obj = conn.makefile(mode='r')
        session: Optional[Session] = None
        process_id = None
        role = None
        
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
            
            with self.lock:
                if session_id not in self.sessions:
                    self.sessions[session_id] = Session(session_id, script or "")
                session = self.sessions[session_id]
            
            if role == "shim-control":
                with session.lock:
                    session.shim_conn = conn
                if process_id is not None:
                    self.dashim_pid_map[process_id] = (session_id, conn)
                    self._track_process(role, process_id, script, session_id)
            elif role == "ui":
                with session.lock:
                    session.ui_conns.add(conn)
                self.broadcast_process_list_to_all_uis()
            
            self.conn_info[conn] = {"role": role, "session_id": session_id, "process_id": process_id}
            self.send_json(conn, {"type": "session_id", "session_id": session_id, "script": session.script_name})
            
            # Main message loop
            try:
                for line in file_obj:
                    print(f"[develop_server] Raw line received: {line!r}")
                    try:
                        msg = json.loads(line.strip())
                    except Exception as e:
                        print(f"[develop_server] Error parsing JSON: {e}")
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
                    elif msg.get("type") == "updateNode":
                        # Update the node in the process's graph
                        sid = msg.get("session_id")
                        node_id = msg.get("nodeId")
                        field = msg.get("field")
                        value = msg.get("value")
                        
                        # Find the process by session_id
                        for pid, info in self.process_info.items():
                            if info.get("session_id") == sid and info.get("graph"):
                                nodes = info["graph"].get("nodes", [])
                                for i, node in enumerate(nodes):
                                    if node.get("id") == node_id:
                                        # Deep copy node before mutation
                                        new_node = dict(node)
                                        new_node[field] = value
                                        nodes[i] = new_node
                                        print(f"[develop_server] Updated node {node_id} field '{field}' to '{value}' in process {pid}")
                                        break
                                else:
                                    print(f"[develop_server] Warning: Node {node_id} not found in graph for process {pid}")
                                break
                        else:
                            print(f"[develop_server] Warning: No process found with session_id {sid}")
                        
                        self.broadcast_process_list_to_all_uis()
                        continue
                    else:
                        self.route_message(conn, msg)
                        
            except (ConnectionResetError, OSError) as e:
                print(f"[develop_server] Connection closed: {e}")
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
                            # Only remove from process info if shim-runner
                            self._mark_process_finished(info.get("role"), pid)
                elif info["role"] == "ui":
                    with session.lock:
                        session.ui_conns.discard(conn)
            try:
                conn.close()
            except Exception as e:
                print(f"[develop_server] Error closing connection: {e}")
    
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
