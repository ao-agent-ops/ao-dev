import re
import socket
import os
import json
import threading
import subprocess
import time
import uuid
import subprocess
import shlex
from datetime import datetime
from typing import Optional
from aco.server.edit_manager import EDIT
from aco.server.cache_manager import CACHE
from aco.server import db
from aco.common.logger import logger
from aco.common.constants import ACO_CONFIG, ACO_LOG_PATH, HOST, PORT
from aco.server.telemetry.server_logger import log_server_message, log_shim_control_registration


def send_json(conn: socket.socket, msg: dict) -> None:
    try:
        msg_type = msg.get("type", "unknown")
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
        self.rerun_sessions = set()  # Track sessions being rerun to avoid clearing llm_calls

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

    def broadcast_experiment_list_to_uis(self, conn=None) -> None:
        """Only broadcast to one UI (conn) or, if conn is None, to all."""
        # Get all experiments from database (already sorted by name ASC)
        db_experiments = CACHE.get_all_experiments_sorted()

        # Create a map of session_id to session for quick lookup
        session_map = {session.session_id: session for session in self.sessions.values()}

        experiment_list = []
        for row in db_experiments:
            session_id = row["session_id"]
            session = session_map.get(session_id)

            # Get status from in-memory session, or default to "finished"
            status = session.status if session else "finished"

            # Get data from DB entries.
            timestamp = row["timestamp"]
            title = row["name"]
            success = row["success"]
            notes = row["notes"]
            log = row["log"]

            # Parse color_preview from database
            color_preview = []
            if row["color_preview"]:
                try:
                    color_preview = json.loads(row["color_preview"])
                except:
                    color_preview = []

            experiment_list.append(
                {
                    "session_id": session_id,
                    "status": status,
                    "timestamp": timestamp,
                    "color_preview": color_preview,
                    "title": title,
                    "success": success,
                    "notes": notes,
                    "log": log,
                }
            )

        msg = {"type": "experiment_list", "experiments": experiment_list}
        if conn:
            send_json(conn, msg)
        else:
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
            # Mark as finished (not running)
            session = self.sessions.get(session_id)
            if not session:
                session = Session(session_id)
                session.status = "finished"
                self.sessions[session_id] = session

    def handle_graph_request(self, conn, session_id):
        # Query graph_topology for the session and reconstruct the in-memory graph
        row = CACHE.get_graph(session_id)
        if row and row["graph_topology"]:
            graph = json.loads(row["graph_topology"])
            self.session_graphs[session_id] = graph
            send_json(conn, {"type": "graph_update", "session_id": session_id, "payload": graph})

    def _determine_unique_tab_title(self, label, session_id):
        # Search for strings like f"{label}" and f"{label} (x)".
        pattern = rf"^{re.escape(label)}(?: \((\d+)\))?$"
        matches = []
        for string in [n["tab_title"] for n in self.session_graphs[session_id]["nodes"]]:
            if re.match(pattern, string):
                matches.append(string)

        # Form unique tab title.
        if len(matches) == 0:
            return label
        return f"{label} ({len(matches)})"

    def _find_session_with_node(self, node_id: str) -> Optional[str]:
        """Find which session contains a specific node ID"""
        source_sessions = set()
        for session_id, graph in self.session_graphs.items():
            for node in graph["nodes"]:
                if node["id"] == node_id:
                    source_sessions.add(session_id)
        return source_sessions

    def handle_add_node(self, msg: dict) -> None:
        sid = msg["session_id"]
        node = msg["node"]
        incoming_edges = msg.get("incoming_edges", [])

        # Check if any incoming edges reference nodes from other sessions
        cross_session_sources = []
        target_sessions = set()

        for source in incoming_edges:
            # Find which session contains this source node
            source_sessions = self._find_session_with_node(source)
            if source_sessions:
                for source_session in source_sessions:
                    target_sessions.add(source_session)
                    cross_session_sources.append(source)
                    logger.info(
                        f"Found cross-session edge: node {source} in session {source_session}"
                    )

        # If we have cross-session references, add the node to those sessions instead of current session
        if target_sessions:
            logger.info(f"Adding node {node['id']} to cross-session targets: {target_sessions}")
            for target_sid in target_sessions:
                self._add_node_to_session(target_sid, node, cross_session_sources)
        else:
            # No cross-session references, add to current session as normal
            self._add_node_to_session(sid, node, incoming_edges)

    def _add_node_to_session(self, sid: str, node: dict, incoming_edges: list) -> None:
        """Add a node to a specific session's graph"""
        # Add or update the node
        graph = self.session_graphs.setdefault(sid, {"nodes": [], "edges": []})
        for n in graph["nodes"]:
            if n["id"] == node["id"]:
                break
        else:
            # Get title for tab where user edits input/output.
            tab_title = self._determine_unique_tab_title(node["label"], sid)
            node["tab_title"] = tab_title
            graph["nodes"].append(node)
            logger.info(f"Added node {node['id']} to session {sid}")

        # Add incoming edges (only if source nodes exist in the graph)
        existing_node_ids = {n["id"] for n in graph["nodes"]}
        for source in incoming_edges:
            if source in existing_node_ids:
                target = node["id"]
                edge_id = f"e{source}-{target}"
                full_edge = {"id": edge_id, "source": source, "target": target}
                graph["edges"].append(full_edge)
                logger.info(f"Added edge {edge_id} in session {sid}")
            else:
                logger.debug(f"Skipping edge from non-existent node {source} to {node['id']}")

        # Update color preview in database
        node_colors = [n["border_color"] for n in graph["nodes"]]
        color_preview = node_colors[-6:]  # Only display last 6 colors
        CACHE.update_color_preview(sid, color_preview)
        # Broadcast color preview update to all UIs
        self.broadcast_to_all_uis(
            {"type": "color_preview_update", "session_id": sid, "color_preview": color_preview}
        )
        self.broadcast_to_all_uis(
            {
                "type": "graph_update",
                "session_id": sid,
                "payload": {"nodes": graph["nodes"], "edges": graph["edges"]},
            }
        )
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
            self.broadcast_to_all_uis(
                {
                    "type": "graph_update",
                    "session_id": session_id,
                    "payload": self.session_graphs[session_id],
                }
            )
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
            self.broadcast_to_all_uis(
                {
                    "type": "graph_update",
                    "session_id": session_id,
                    "payload": self.session_graphs[session_id],
                }
            )
        logger.debug("Output overwrite completed")

    def handle_log(self, msg: dict) -> None:
        session_id = msg["session_id"]
        success = msg["success"]
        entry = msg["entry"]
        EDIT.add_log(session_id, success, entry)

        self.broadcast_experiment_list_to_uis()

    def handle_get_graph(self, msg: dict, conn: socket.socket) -> None:
        session_id = msg["session_id"]

        self.handle_graph_request(conn, session_id)

    def handle_add_subrun(self, msg: dict, conn: socket.socket) -> None:
        # If rerun, use previous session_id. Else, assign new one.
        prev_session_id = msg.get("prev_session_id")
        if prev_session_id is not None:
            session_id = prev_session_id
        else:
            session_id = str(uuid.uuid4())
            # Insert new experiment into DB.
            cwd = msg.get("cwd")
            command = msg.get("command")
            environment = msg.get("environment")
            timestamp = datetime.now().strftime("%d/%m %H:%M")
            name = msg.get("name")
            parent_session_id = msg.get("parent_session_id")
            EDIT.add_experiment(
                session_id,
                name,
                timestamp,
                cwd,
                command,
                environment,
                parent_session_id,
            )
        # Insert session if not present.
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = Session(session_id)
            session = self.sessions[session_id]
        with session.lock:
            session.shim_conn = conn
        session.status = "running"
        self.broadcast_experiment_list_to_uis()
        self.conn_info[conn] = {"role": "shim-control", "session_id": session_id}
        send_json(conn, {"type": "session_id", "session_id": session_id})

    def handle_erase(self, msg):
        session_id = msg.get("session_id")

        EDIT.erase(session_id)
        # Clear color preview in database
        CACHE.update_color_preview(session_id, [])

        # Broadcast color preview clearing to all UIs
        self.broadcast_to_all_uis(
            {"type": "color_preview_update", "session_id": session_id, "color_preview": []}
        )

        self.handle_restart_message({"session_id": session_id})

    def handle_restart_message(self, msg: dict) -> bool:
        child_session_id = msg.get("session_id")
        session_id = CACHE.get_parent_session_id(child_session_id)
        if not session_id:
            logger.error("Restart message missing session_id. Ignoring.")
            return
        session = self.sessions.get(session_id)

        # Reset color previews.
        CACHE.update_color_preview(child_session_id, [])
        self.broadcast_to_all_uis(
            {"type": "color_preview_update", "session_id": session_id, "color_preview": []}
        )

        # Immediately broadcast an empty graph to all UIs for fast clearing
        self.session_graphs[child_session_id] = {"nodes": [], "edges": []}
        self.broadcast_to_all_uis(
            {
                "type": "graph_update",
                "session_id": child_session_id,
                "payload": {"nodes": [], "edges": []},
            }
        )

        if session and session.status == "running":
            if session.shim_conn:
                restart_msg = {"type": "restart", "session_id": session_id}
                logger.debug(
                    f"Sending restart to shim-control for session_id: {session_id} with message: {restart_msg}"
                )
                try:
                    send_json(session.shim_conn, restart_msg)
                except Exception as e:
                    logger.error(f"Error sending restart: {e}")
                return
            else:
                logger.warning(f"No shim_conn for session_id: {session_id}")
        elif session and session.status == "finished":
            # Rerun for finished session: launch new shim-control with same session_id
            cwd, command, environment = CACHE.get_exec_command(session_id)

            logger.debug(
                f"Rerunning finished session {session_id} with cwd={cwd} and command={command}"
            )
            # Mark this session as being rerun to avoid clearing llm_calls
            self.rerun_sessions.add(child_session_id)
            try:
                # Insert session_id into environment so shim-control uses the same session_id
                env = os.environ.copy()
                env["AGENT_COPILOT_SESSION_ID"] = session_id

                # Restore the user's original environment variables
                env.update(environment)
                logger.debug(
                    f"Restored {len(environment)} environment variables for session {session_id}"
                )

                # Rerun the original command. This starts the shim-control, which starts the shim-runner.
                args = shlex.split(command)
                EDIT.update_graph_topology(child_session_id, self.session_graphs[child_session_id])
                subprocess.Popen(args, cwd=cwd, env=env, close_fds=True, start_new_session=True)

                # Update the session status to running and update timestamp for rerun
                session = self.sessions.get(child_session_id)
                if session:
                    session.status = "running"
                    # Update database timestamp so it sorts correctly
                    new_timestamp = datetime.now().strftime("%d/%m %H:%M")
                    EDIT.update_timestamp(child_session_id, new_timestamp)
                    # Broadcast updated experiment list with rerun session at the front
                    self.broadcast_experiment_list_to_uis()
            except Exception as e:
                logger.error(f"Failed to rerun finished session: {e}")

    def handle_deregister_message(self, msg: dict) -> bool:
        session_id = msg["session_id"]
        session = self.sessions.get(session_id)
        if session:
            session.status = "finished"
            self.broadcast_experiment_list_to_uis()

    def handle_debugger_restart_message(self, msg: dict) -> bool:
        """Handle debugger restart notification, update session info."""
        # TODO: Test
        session_id = msg["session_id"]
        if session_id in self.sessions:
            self.broadcast_experiment_list_to_uis()

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
        self.broadcast_experiment_list_to_uis()
        self.broadcast_to_all_uis(
            {"type": "graph_update", "session_id": None, "payload": {"nodes": [], "edges": []}}
        )
        os.remove(ACO_LOG_PATH)
        logger.info("Database, log file and in-memory state cleared.")

    # ============================================================
    # Message rounting logic.
    # ============================================================

    def process_message(self, msg: dict, conn: socket.socket) -> None:
        # Log the message to telemetry
        log_server_message(msg, self.session_graphs)

        # TODO: Process experiment changes for title, success, notes.
        msg_type = msg.get("type")
        if msg_type == "shutdown":
            self.handle_shutdown()
        elif msg_type == "restart":
            self.handle_restart_message(msg)
        elif msg_type == "deregister":
            self.handle_deregister_message(msg)
        elif msg_type == "debugger_restart":
            self.handle_debugger_restart_message(msg)
        elif msg_type == "add_node":
            self.handle_add_node(msg)
        elif msg_type == "edit_input":
            self.handle_edit_input(msg)
        elif msg_type == "edit_output":
            self.handle_edit_output(msg)
        elif msg_type == "log":
            self.handle_log(msg)
        elif msg_type == "add_subrun":
            self.handle_add_subrun(msg, conn)
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
        logger.info("Registering new session.")
        file_obj = conn.makefile(mode="r")
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
            # Only assign session_id for shim-control.
            if role == "shim-control":
                # If rerun, use previous session_id. Else, assign new one.
                # NOTE: For the BIRD user study, prev_session_id is always set.
                session_id = handshake.get("prev_session_id")
                logger.info(f"Registering session_id {session_id}")
                assert session_id is not None

                # Check if this session actually exists in database
                existing_session = CACHE.get_session_name(session_id)
                if existing_session:
                    # Only clear llm_calls if this is not a rerun from the UI
                    if session_id not in self.rerun_sessions:
                        # Session exists, clear all LLM call entries for this session_id
                        db.execute("DELETE FROM llm_calls WHERE session_id=?", (session_id,))
                        # Also clear the in-memory graph representation
                        self.session_graphs[session_id] = {"nodes": [], "edges": []}
                    else:
                        # Remove from rerun set now that we've handled it
                        self.rerun_sessions.discard(session_id)

                # Session doesn't exist in DB, create it
                cwd = handshake.get("cwd")
                command = handshake.get("command")
                environment = handshake.get("environment")
                timestamp = datetime.now().strftime("%d/%m %H:%M")
                name = handshake.get("name")
                EDIT.add_experiment(
                    session_id,
                    name,
                    timestamp,
                    cwd,
                    command,
                    environment,
                )

                # Insert session if not present.
                with self.lock:
                    if session_id not in self.sessions:
                        self.sessions[session_id] = Session(session_id)
                    session = self.sessions[session_id]
                with session.lock:
                    session.shim_conn = conn
                session.status = "running"
                self.broadcast_experiment_list_to_uis()
                self.conn_info[conn] = {"role": role, "session_id": session_id}
                send_json(conn, {"type": "session_id", "session_id": session_id})

                # Log shim-control registration to telemetry
                log_shim_control_registration(handshake, session_id)
            elif role == "shim-runner":
                pass  # Don't do anything if shim-runner
            elif role == "ui":
                # Always reload finished runs from the DB before sending experiment list
                self.load_finished_runs()
                self.ui_connections.add(conn)
                # Send session_id and config_path to this UI connection (None for UI)
                self.conn_info[conn] = {"role": role, "session_id": None}
                send_json(
                    conn, {"type": "session_id", "session_id": None, "config_path": ACO_CONFIG}
                )
                # Send experiment_list only to this UI connection
                self.broadcast_experiment_list_to_uis(conn)

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
                    self.broadcast_experiment_list_to_uis()
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

        # Try binding with retry logic and better error handling
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.server_sock.bind((HOST, PORT))
                break
            except OSError as e:
                if e.errno == 48 and attempt < max_retries - 1:  # Address already in use
                    logger.warning(
                        f"Port {PORT} in use, retrying in 2 seconds... (attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(2)
                    continue
                else:
                    raise

        self.server_sock.listen()
        logger.info(f"Develop server listening on {HOST}:{PORT}")

        # Load finished runs on startup
        self.load_finished_runs()

        try:
            while True:
                conn, _ = self.server_sock.accept()
                threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
        except OSError:
            # This will be triggered when server_sock is closed (on shutdown)
            pass
        finally:
            self.server_sock.close()
            logger.info("Develop server stopped.")
