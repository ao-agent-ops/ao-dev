import socket
import sys
import os
import argparse
import json
import threading
import subprocess
import select
import uuid
from typing import Dict, Any, Optional

# Default host/port for the server socket
HOST = '127.0.0.1'
PORT = 5959

# Global state for tracking connected clients and LLM call records
clients = {
    "shim_control": [],  # shim controller connections (orchestrators)
    "shim_runner": [],   # shim runner connections (sending call data)
    "extension": []      # extension client connections
}
calls = []              # list of recorded LLM call details (with assigned IDs)
call_id_counter = 1     # incremental ID generator for calls

# --- Data Structures ---

# Each session represents a running develop process and its associated UI clients
class Session:
    def __init__(self, session_id: str, script_name: str):
        self.session_id = session_id
        self.script_name = script_name
        self.shim_conn: Optional[socket.socket] = None
        self.ui_conns: set[socket.socket] = set()
        self.lock = threading.Lock()  # To protect concurrent access

# Map session_id to Session
sessions: Dict[str, Session] = {}

# Map socket to (role, session_id)
conn_info: Dict[socket.socket, Dict[str, Any]] = {}

# --- Helper Functions ---
def send_json(conn: socket.socket, msg: dict):
    try:
        conn.sendall((json.dumps(msg) + "\n").encode("utf-8"))
    except Exception:
        pass

def broadcast_to_uis(session: Session, msg: dict):
    for ui_conn in list(session.ui_conns):
        try:
            send_json(ui_conn, msg)
        except Exception:
            session.ui_conns.discard(ui_conn)

def route_message(sender: socket.socket, msg: dict):
    info = conn_info.get(sender)
    if not info:
        return
    role = info["role"]
    session_id = info["session_id"]
    session = sessions.get(session_id)
    if not session:
        return
    # Route based on sender role
    if role == "ui":
        # UI → Shim
        if session.shim_conn:
            send_json(session.shim_conn, msg)
    elif role == "shim":
        # Shim → all UIs
        broadcast_to_uis(session, msg)

# Dummy user_edit function that the extension can invoke (via a socket message).
# It notifies the shim (via its control connection) that the user edited a prompt.
def user_edit(llm_call_id: int, new_input: str) -> None:
    """
    Handle a user edit request by instructing the shim to restart the user process.
    In practice, the VS Code extension would call this (e.g. via a socket message),
    and it sends a restart signal to the shim along with the edited input.
    """
    message = {"type": "restart", "id": llm_call_id, "new_input": new_input}
    data = (json.dumps(message) + "\n").encode('utf-8')
    # Send the restart instruction to all connected shim controllers
    with threading.Lock():  # ensure thread-safe sending
        for conn in list(clients.get("shim_control", [])):
            print("send to shim")
            try:
                conn.sendall(data)
            except Exception:
                # Remove disconnected clients
                clients["shim_control"].remove(conn)

# Helper: handle a new client connection in a separate thread
def handle_client(conn: socket.socket, addr):
    print(f"New client connection from {addr}")
    file_obj = conn.makefile(mode='r')
    session: Optional[Session] = None
    try:
        # Expect handshake first
        handshake_line = file_obj.readline()
        if not handshake_line:
            return
        handshake = json.loads(handshake_line.strip())
        role = handshake.get("role")
        script = handshake.get("script")
        session_id = handshake.get("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
        with threading.Lock():
            if session_id not in sessions:
                sessions[session_id] = Session(session_id, script or "")
            session = sessions[session_id]
        if role == "shim-runner" or role == "shim-control":
            with session.lock:
                session.shim_conn = conn
        elif role == "ui":
            with session.lock:
                session.ui_conns.add(conn)
        conn_info[conn] = {"role": role, "session_id": session_id}
        send_json(conn, {"type": "session_id", "session_id": session_id, "script": session.script_name})
        # Main message loop
        try:
            for line in file_obj:
                try:
                    msg = json.loads(line.strip())
                except Exception:
                    continue
                if "session_id" not in msg:
                    msg["session_id"] = session_id
                # If this is a shutdown message, close all sockets and exit process
                if msg.get("type") == "shutdown":
                    print("[develop_server] Shutdown command received. Closing all connections.")
                    # Close all client sockets
                    for s in list(conn_info.keys()):
                        print(f"Closing socket: {s}")
                        try:
                            s.close()
                        except Exception as e:
                            print(f"Error closing socket: {e}")
                            pass
                    # Close the main server socket if accessible
                    os._exit(0)  # Immediately exit the process
                route_message(conn, msg)
        except (ConnectionResetError, OSError):
            # Socket closed, exit thread quietly
            pass
    finally:
        info = conn_info.pop(conn, None)
        if info and session:
            if info["role"] == "shim":
                with session.lock:
                    session.shim_conn = None
            elif info["role"] == "ui":
                with session.lock:
                    session.ui_conns.discard(conn)
        try:
            conn.close()
        except Exception:
            pass

# Main server loop: accept clients and spawn handler threads
def run_server():
    global server_sock
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen()
    print(f"Develop server listening on {HOST}:{PORT}")
    try:
        while True:
            conn, addr = server_sock.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except OSError:
        # This will be triggered when server_sock is closed (on shutdown)
        pass
    finally:
        server_sock.close()
        print("Develop server stopped.")

# CLI entry point
def main():
    parser = argparse.ArgumentParser(description="Development server for LLM call visualization")
    parser.add_argument('command', choices=['start', 'stop', 'edit'], help="Start or stop the server")
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
        # Using start_new_session=True will call setsid() in the child process:contentReference[oaicite:0]{index=0}.
        print("Develop server started.")
    elif args.command == 'stop':
        # Connect to the server and send a shutdown command
        try:
            sock = socket.create_connection((HOST, PORT), timeout=3)
            # Send handshake
            handshake = {"type": "hello", "role": "ui", "script": "stopper"}
            sock.sendall((json.dumps(handshake) + "\n").encode('utf-8'))
            # Send shutdown message
            sock.sendall((json.dumps({"type": "shutdown"}) + "\n").encode('utf-8'))
            sock.close()
            print("Develop server stop signal sent.")
        except Exception:
            print("No running server found.")
            sys.exit(1)
    elif args.command == '--serve':
        # Internal: run the server loop (not meant to be called by users directly)
        run_server()

    # DEBUG: Call from VS Code extension in the future.
    elif args.command == 'edit':
        user_edit(llm_call_id=42, new_input="hello 42")


if __name__ == "__main__":
    # Support internal "--serve" invocation to actually run the server loop
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        run_server()
    else:
        print(f"[develop_server] Starting server on {HOST}:{PORT}, PID={os.getpid()}")
        main()
