import socket
import sys
import os
import argparse
import json
import threading
import subprocess
import uuid
import time
import subprocess
import shlex
from datetime import datetime
from typing import Dict, Any, Optional, Set, Tuple
from workflow_edits.edit_manager import EDIT
from workflow_edits.cache_manager import CACHE
from common.logger import logger


# Configuration constants
HOST = '127.0.0.1'
PORT = 5959
SOCKET_TIMEOUT = 3
SHUTDOWN_WAIT = 2


def send_json(conn: socket.socket, msg: dict) -> None:
    try:
        msg_type = msg.get('type', 'unknown')
        logger.debug(f"Sent message type: {msg_type}")
        conn.sendall((json.dumps(msg) + "\n").encode("utf-8"))
    except Exception as e:
        logger.error(f"Error sending JSON: {e}")

class Session:
    """Represents a running develop process and its associated UI clients."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.shim_conn: Optional[socket.socket] = None
        self.status = "running"
        self.timestamp = datetime.now().strftime("%d/%m %H:%M")
        self.lock = threading.Lock()

class DevelopServer:
    """Manages the development server for LLM call visualization."""
    
    def __init__(self):
        self.server_sock = None
        self.lock = threading.Lock()
        self.conn_info = {}  # conn -> {role, session_id}
        self.session_graphs = {}  # session_id -> graph_data
        self.ui_connections = set()  # All UI connections (simplified)
        self.sessions = {}  # session_id -> Session (only for shim connections)
        # Store a pending rerun session_id if a rerun is requested
        self.pending_rerun_session_id = None
    
    # ============================================================
    # Utils
    # ============================================================

    def broadcast_to_all_uis(self, msg: dict) -> None:
        """Broadcast a message to all UI connections."""
        for ui_conn in list(self.ui_connections):
            try:
                send_json(ui_conn, msg)
            except Exception as e:
                logger.error(f"Error broadcasting to UI: {e}")
                self.ui_connections.discard(ui_conn)
    
    def broadcast_experiment_list_to_all_uis(self) -> None:
        experiment_list = [
            {
                "session_id": session.session_id,
                "status": session.status,
                "timestamp": session.timestamp
            }
            for session in self.sessions.values()
        ]
        msg = {"type": "experiment_list", "experiments": experiment_list}
        self.broadcast_to_all_uis(msg)
    
    def print_graph(self, session_id):
        # Debug utility.
        print("\n--------------------------------")
        # Print list of all sessions and their status.
        for session_id, session in self.sessions.items():
            print(f"Session {session_id}: {session.status}")

        # Print graph for the given session_id.
        print(f"\nGraph for session_id: {session_id}")
        graph = self.session_graphs.get(session_id)
        if graph:
            print(json.dumps(graph, indent=4))
        else:
            print(f"No graph found for session_id: {session_id}")
        print("--------------------------------\n")
    # ============================================================
    # Handle message types.
    # ============================================================

    def load_finished_runs(self):
        # Load only session_id and timestamp for finished runs
        rows = CACHE.get_finished_runs()
        for row in rows:
            session_id = row["session_id"]
            timestamp = row["timestamp"]
            # Mark as finished (not running)
            session = self.sessions.get(session_id)
            if not session:
                session = Session(session_id)
                session.status = "finished"
                session.timestamp = timestamp
                self.sessions[session_id] = session

    def handle_graph_request(self, conn, session_id):
        # Query graph_topology for the session and reconstruct the in-memory graph
        row = CACHE.get_graph(session_id)
        if row and row["graph_topology"]:
            graph = json.loads(row["graph_topology"])
            self.session_graphs[session_id] = graph
            send_json(conn, {
                "type": "graph_update",
                "session_id": session_id,
                "payload": graph
            })
    
    def handle_add_node(self, msg: dict) -> None:
        sid = msg["session_id"]
        node = msg["node"]
        if "model" not in node:
            node["model"] = None
        if "id" not in node:
            node["id"] = str(uuid.uuid4())
        if "api_type" not in node:
            node["api_type"] = None
        graph = self.session_graphs.setdefault(sid, {"nodes": [], "edges": []})
        for i, n in enumerate(graph["nodes"]):
            if n["id"] == node["id"]:
                graph["nodes"][i] = node
                break
        else:
            graph["nodes"].append(node)
        self.broadcast_to_all_uis({
            "type": "graph_update",
            "session_id": sid,
            "payload": {"nodes": graph["nodes"], "edges": graph["edges"]}
        })
        EDIT.update_graph_topology(sid, graph)

    def handle_add_edge(self, msg: dict) -> None:
        sid = msg["session_id"]
        edge = msg["edge"]
        graph = self.session_graphs.setdefault(sid, {"nodes": [], "edges": []})
        if not any(e["source"] == edge["source"] and e["target"] == edge["target"] for e in graph["edges"]):
            edge_id = f"e{edge['source']}-{edge['target']}"
            edge_with_id = {"id": edge_id, **edge}
            graph["edges"].append(edge_with_id)
        self.broadcast_to_all_uis({
            "type": "graph_update",
            "session_id": sid,
            "payload": {"nodes": graph["nodes"], "edges": graph["edges"]}
        })
        EDIT.update_graph_topology(sid, graph)

    def handle_edit_input(self, msg: dict) -> None:
        logger.debug(f"Received edit_input: {msg}")
        session_id = msg["session_id"]
        node_id = msg["node_id"]
        new_input = msg["value"]
        EDIT.set_input_overwrite(session_id, node_id, new_input)
        if session_id in self.session_graphs:
            for node in self.session_graphs[session_id]["nodes"]:
                if node["id"] == node_id:
                    node["input"] = new_input
                    break
            self.broadcast_to_all_uis({
                "type": "graph_update",
                "session_id": session_id,
                "payload": self.session_graphs[session_id]
            })
        logger.debug("Input overwrite completed")

    def handle_edit_output(self, msg: dict) -> None:
        logger.debug(f"Received edit_output: {msg}")
        session_id = msg["session_id"]
        node_id = msg["node_id"]
        new_output = msg["value"]
        EDIT.set_output_overwrite(session_id, node_id, new_output)
        if session_id in self.session_graphs:
            for node in self.session_graphs[session_id]["nodes"]:
                if node["id"] == node_id:
                    node["output"] = new_output
                    break
            self.broadcast_to_all_uis({
                "type": "graph_update",
                "session_id": session_id,
                "payload": self.session_graphs[session_id]
            })
        logger.debug("Output overwrite completed")

    def handle_get_graph(self, msg: dict, conn: socket.socket) -> None:
        self.handle_graph_request(conn, msg["session_id"])

    def handle_erase(self, msg):
        session_id = msg.get("session_id")
        EDIT.erase(session_id)
        self.handle_restart_message({"session_id": session_id})

    def handle_restart_message(self, msg: dict) -> bool:
        session_id = msg.get("session_id")
        if not session_id:
            logger.error("Restart message missing session_id. Ignoring.")
            return
        session = self.sessions.get(session_id)
        if session and session.status == "running":
            # Immediately broadcast an empty graph to all UIs for fast clearing
            self.session_graphs[session_id] = {"nodes": [], "edges": []}
            logger.debug(f"(pre-restart) Graph reset for session_id: {session_id}")
            self.broadcast_to_all_uis({
                "type": "graph_update",
                "session_id": session_id,
                "payload": {"nodes": [], "edges": []}
            })
            if session.shim_conn:
                restart_msg = {"type": "restart", "session_id": session_id}
                logger.debug(f"Sending restart to shim-control for session_id: {session_id} with message: {restart_msg}")
                try:
                    send_json(session.shim_conn, restart_msg)
                except Exception as e:
                    logger.error(f"Error sending restart: {e}")
                return
            else:
                logger.warning(f"No shim_conn for session_id: {session_id}")
        elif session and session.status == "finished":
            # For finished rerun, store the session_id for the next shim-control
            self.pending_rerun_session_id = session_id
            # Rerun for finished session: launch new shim-control with same session_id
            cwd, command = CACHE.get_exec_command(session_id)
            if not cwd:
                logger.error(f"Requested restart for session without logged command.")
                return

            logger.debug(f"Rerunning finished session {session_id} with cwd={cwd} and command={command}")
            try:
                # Insert session_id into environment so shim-control uses the same session_id
                env = os.environ.copy()
                env["AGENT_COPILOT_SESSION_ID"] = session_id
                # Rerun the original command. This starts the shim-control, which starts the shim-runner.
                args = shlex.split(command)
                subprocess.Popen(args, cwd=cwd, env=env, close_fds=True, start_new_session=True)
                # Immediately broadcast an empty graph to all UIs for fast clearing
                self.session_graphs[session_id] = {"nodes": [], "edges": []}
                self.broadcast_to_all_uis({
                    "type": "graph_update",
                    "session_id": session_id,
                    "payload": {"nodes": [], "edges": []}
                })
            except Exception as e:
                logger.error(f"Failed to rerun finished session: {e}")
    
    def handle_deregister_message(self, msg: dict) -> bool:
        session_id = msg["session_id"]
        session = self.sessions.get(session_id)
        if session:
            session.status = "finished"
            self.broadcast_experiment_list_to_all_uis()
    
    def handle_debugger_restart_message(self, msg: dict) -> bool:
        """Handle debugger restart notification, update session info."""
        # TODO: Test
        session_id = msg["session_id"]
        if session_id in self.sessions:
            self.broadcast_experiment_list_to_all_uis()
    
    def handle_shutdown(self) -> None:
        """Handle shutdown command by closing all connections."""
        logger.info("Shutdown command received. Closing all connections.")
        # Close all client sockets
        for s in list(self.conn_info.keys()):
            logger.debug(f"Closing socket: {s}")
            try:
                s.close()
            except Exception as e:
                logger.error(f"Error closing socket: {e}")
        os._exit(0)

    def handle_clear(self):
        CACHE.clear_db()
        self.session_graphs.clear()
        self.sessions.clear()
        self.broadcast_experiment_list_to_all_uis()
        self.broadcast_to_all_uis({"type": "graph_update", "session_id": None, "payload": {"nodes": [], "edges": []}})
        logger.info("All database records and in-memory state cleared.")

    # ============================================================
    # Message rounting logic.
    # ============================================================

    def process_message(self, msg: dict, conn: socket.socket) -> None:
        msg_type = msg.get("type")
        if msg_type == "shutdown":
            self.handle_shutdown()
        elif msg_type == "restart":
            self.handle_restart_message(msg)
        elif msg_type == "deregister":
            self.handle_deregister_message(msg)
        elif msg_type == "debugger_restart":
            self.handle_debugger_restart_message(msg)
        elif msg_type == "addNode":
            self.handle_add_node(msg)
        elif msg_type == "addEdge":
            self.handle_add_edge(msg)
        elif msg_type == "edit_input":
            self.handle_edit_input(msg)
        elif msg_type == "edit_output":
            self.handle_edit_output(msg)
        elif msg_type == "get_graph":
            self.handle_get_graph(msg, conn)
        elif msg_type == "erase":
            self.handle_erase(msg)
        elif msg_type == "clear":
            self.handle_clear()
        else:
            logger.error(f"Unknown message type. Message:\n{msg}")
    
    def handle_client(self, conn: socket.socket) -> None:
        """Handle a new client connection in a separate thread."""
        file_obj = conn.makefile(mode='r')
        session: Optional[Session] = None
        role = None
        
        try:
            # Expect handshake first
            handshake_line = file_obj.readline()
            if not handshake_line:
                return
            handshake = json.loads(handshake_line.strip())
            role = handshake.get("role")
            session_id = None
            # Only assign session_id for shim-control
            if role == "shim-control":
                if self.pending_rerun_session_id:
                    session_id = self.pending_rerun_session_id
                    self.pending_rerun_session_id = None
                else:
                    session_id = str(uuid.uuid4())
                with self.lock:
                    if session_id not in self.sessions:
                        self.sessions[session_id] = Session(session_id)
                        # Insert new experiment row using edit_manager
                        cwd = handshake.get("cwd")
                        command = handshake.get("command")
                        timestamp = datetime.now().strftime("%d/%m %H:%M")
                        EDIT.add_experiment(session_id, timestamp, cwd, command)
                    session = self.sessions[session_id]
                with session.lock:
                    session.shim_conn = conn
                session.status = "running"
                session.timestamp = datetime.now().strftime("%d/%m %H:%M")
                self.broadcast_experiment_list_to_all_uis()
                self.conn_info[conn] = {"role": role, "session_id": session_id}
                send_json(conn, {"type": "session_id", "session_id": session_id})
            elif role == "shim-runner":
                session_id = handshake.get("session_id")
                # Optionally, associate this runner with the session if needed
                pass  # Do not add to self.ui_connections
            elif role == "ui":
                # Always reload finished runs from the DB before sending experiment list
                self.load_finished_runs()
                self.ui_connections.add(conn)
                # Send session_id to this UI connection (None for UI)
                self.conn_info[conn] = {"role": role, "session_id": None}
                send_json(conn, {"type": "session_id", "session_id": None})
                # Send experiment_list only to this UI connection
                experiment_list = [
                    {
                        "session_id": session.session_id,
                        "status": session.status,
                        "timestamp": session.timestamp
                    }
                    for session in self.sessions.values()
                ]
                send_json(conn, {"type": "experiment_list", "experiments": experiment_list})
                # Send current graph data for all running sessions to the new UI
                for sid, session in self.sessions.items():
                    if session.status == "running" and sid in self.session_graphs:
                        graph_data = self.session_graphs[sid]
                        if graph_data.get("nodes") or graph_data.get("edges"):
                            send_json(conn, {
                                "type": "graph_update",
                                "session_id": sid,
                                "payload": graph_data
                            })
            
            # Main message loop
            try:
                for line in file_obj:
                    try:
                        msg = json.loads(line.strip())
                    except Exception as e:
                        logger.error(f"Error parsing JSON: {e}")
                        continue
                    
                    # Print message type.
                    msg_type = msg.get("type", "unknown")
                    logger.debug(f"Received message type: {msg_type}")

                    if "session_id" not in msg:
                        msg["session_id"] = session_id
                    
                    self.process_message(msg, conn)
                        
            except (ConnectionResetError, OSError) as e:
                logger.info(f"Connection closed: {e}")
        finally:
            # Clean up connection
            info = self.conn_info.pop(conn, None)
            # Only mark session finished for shim-control disconnects
            if info and role == "shim-control":
                session = self.sessions.get(info["session_id"])
                if session:
                    with session.lock:
                        session.shim_conn = None
                    session.status = "finished"
                    self.broadcast_experiment_list_to_all_uis()
            elif info and role == "ui":
                # Remove from global UI connections list
                self.ui_connections.discard(conn)
            try:
                conn.close()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
    
    def run_server(self) -> None:
        """Main server loop: accept clients and spawn handler threads."""
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((HOST, PORT))
        self.server_sock.listen()
        logger.info(f"Develop server listening on {HOST}:{PORT}")

        # Load finished runs on startup
        self.load_finished_runs()

        try:
            while True:
                conn, addr = self.server_sock.accept()
                threading.Thread(
                    target=self.handle_client,
                    args=(conn,),
                    daemon=True
                ).start()
        except OSError:
            # This will be triggered when server_sock is closed (on shutdown)
            pass
        finally:
            self.server_sock.close()
            logger.info("Develop server stopped.")


# ============================================================
# CLI (start / stop).
# ============================================================

def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Development server for LLM call visualization")
    parser.add_argument('command', choices=['start', 'stop', 'restart', 'clear'], 
                       help="Start, stop, restart, or clear the server database and state")
    args = parser.parse_args()

    if args.command == 'start':
        # If server is already running, do not start another
        try:
            socket.create_connection((HOST, PORT), timeout=1).close()
            logger.info("Develop server is already running.")
            return
        except Exception:
            pass
        # Launch the server as a detached background process (POSIX)
        subprocess.Popen([sys.executable, __file__, "--serve"],
                        close_fds=True, start_new_session=True)
        logger.info("Develop server started.")
        
    elif args.command == 'stop':
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
        
    elif args.command == 'restart':
        # Stop the server if running
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
        subprocess.Popen([sys.executable, __file__, "--serve"],
                        close_fds=True, start_new_session=True)
        logger.info("Develop server restarted.")
        
    elif args.command == 'clear':
        # Connect to the server and send a clear command
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
        
    elif args.command == '--serve':
        # Internal: run the server loop (not meant to be called by users directly)
        server = DevelopServer()
        server.run_server()

if __name__ == "__main__":
    # Support internal "--serve" invocation to actually run the server loop
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        server = DevelopServer()
        server.run_server()
    else:
        logger.info(f"Starting server on {HOST}:{PORT}, PID={os.getpid()}")
        main()
