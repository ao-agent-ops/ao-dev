"""
Optimization server for handling graph optimization requests.

This server connects to the develop server as a client and handles
optimization-related operations like similarity search.
"""

import socket
import json
import time
import logging
import os
import signal
from typing import Optional, List

from common.constants import ACO_OPT_LOG_PATH
from aco.common.constants import HOST, PORT
from aco.server.database_manager import DB


def setup_optimization_logger():
    """Set up a separate logger for the optimization server."""
    logger = logging.getLogger("OptimizationServer")
    
    # Clear any existing handlers
    if logger.handlers:
        logger.handlers.clear()
    
    logger.setLevel(logging.DEBUG)
    
    # Create file handler for optimization_server.log
    file_handler = logging.FileHandler(ACO_OPT_LOG_PATH, mode='a')
    
    # Create console handler as well
    console_handler = logging.StreamHandler()
    
    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# Set up the optimization server logger
logger = setup_optimization_logger()


from openai import OpenAI

openai_client = OpenAI()


def _text_to_embedding(text: str) -> List[float]:
    """
    Returns a 1536-dim embedding using OpenAI text-embedding-3-small.
    """
    emb = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return emb.data[0].embedding


def send_json(conn: socket.socket, msg: dict) -> None:
    """Send a JSON message over a socket connection."""
    try:
        msg_type = msg.get("type", "unknown")
        logger.debug(f"[OptimizationServer] Sent message type: {msg_type}")
        conn.sendall((json.dumps(msg) + "\n").encode("utf-8"))
    except Exception as e:
        logger.error(f"[OptimizationServer] Error sending JSON: {e}")


class OptimizationClient:
    """
    Optimization client that connects to the develop server.

    This client handles optimization requests from the develop server,
    processing operations like similarity search, clustering, and
    graph transformations.
    """

    def __init__(self):
        self.conn: Optional[socket.socket] = None
        self.running = True
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        logger.debug(f"[OptimizationServer] Signal handlers installed for pid {os.getpid()}")

    def _handle_shutdown_signal(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"[OptimizationServer] Received signal {signum}, shutting down gracefully...")
        self.running = False

    # ============================================================
    # Message Handlers
    # ============================================================

    def handle_add_node(self, msg: dict) -> None:
        """
        Given (session_id, node_id, input_str), compute input_str embedding and
        add to DB.
        """
        session_id = msg.get("session_id")
        node_id = msg.get("node_id")
        input_str = msg.get("input_str")  # embed this string

        if not session_id or not node_id or input_str is None:
            logger.error(f"[OptimizationServer] handle_add_node: missing fields in msg: {msg}")
            return

        try:
            embedding = _text_to_embedding(input_str)
            embedding_json = json.dumps(embedding)
            DB.insert_lesson_embedding_query(session_id, node_id, embedding_json)
            logger.debug(
                f"[OptimizationServer] Stored embedding for session {session_id}, node {node_id}"
            )
        except Exception as e:
            logger.error(
                f"[OptimizationServer] Failed to store embedding for "
                f"session {session_id}, node {node_id}: {e}"
            )


    def handle_similarity_search(self, msg: dict) -> None:
        """
        Given (session_id, node_id) return the k most similar [(session_id, node_id)].
        """
        session_id = msg.get("session_id")  # compute sim to this session_id
        node_id = msg.get("node_id")  # compute sim to this node_id
        top_k = msg.get("k", 10)  # how many similar nodes to fetch

        try:
            # 1. Get target embedding
            row = DB.get_lesson_embedding_query(session_id, node_id)
            logger.info(f"[OptimizationServer] Similarity search: Looking for embedding for session {session_id}, node {node_id}")
            
            if not row or not row["embedding"]:
                logger.warning(f"[OptimizationServer] No embedding found for session {session_id}, node {node_id}")
                # Check if there are any embeddings in the database at all
                all_embeddings_count = len(DB.get_all_lesson_embeddings())
                logger.info(f"[OptimizationServer] Total embeddings in database: {all_embeddings_count}")
                raise AssertionError("Node embedding not present in DB")
                
            target_emb = json.loads(row["embedding"])
            logger.info(f"[OptimizationServer] Found target embedding for session {session_id}, node {node_id}")

            # 2. Get closest vectors using the database backend
            knn_rows = DB.nearest_neighbors_query(
                json.dumps(target_emb),
                top_k
            )
            logger.info(f"[OptimizationServer] Found {len(knn_rows)} potential matches from nearest neighbors query")

            # Convert to result format and return
            results = [
                {
                    "session_id": r["session_id"],
                    "node_id": r["node_id"],
                }
                for r in knn_rows
            ]
            logger.info(f"[OptimizationServer] Found {len(results)} similar experiments")

            response = {
                "type": "similarity_search_result",
                "session_id": session_id,
                "node_id": node_id,
                "results": results,
            }

            send_json(self.conn, response)

        except Exception as e:
            logger.error(f"[SimSearch] Search failed: {e}")
            response = {
                "type": "similarity_search_result",
                "session_id": session_id,
                "node_id": node_id,
                "results": [],
            }
            send_json(self.conn, response)


    def handle_cluster_nodes(self, msg: dict) -> None:
        """Handle clustering request (not yet implemented)."""
        logger.info("[OptimizationServer] Clustering request received (not implemented)")
        # TODO: Implement clustering functionality
        
    def handle_optimize_graph(self, msg: dict) -> None:
        """Handle graph optimization request (not yet implemented)."""
        logger.info("[OptimizationServer] Graph optimization request received (not implemented)")
        # TODO: Implement graph optimization functionality

    def handle_shutdown(self, msg: dict) -> None:
        """Handle shutdown command from develop server."""
        logger.info("[OptimizationServer] Shutdown command received")
        self.running = False

    # ============================================================
    # Message Routing
    # ============================================================

    def process_message(self, msg: dict) -> None:
        """
        Route messages to appropriate handlers based on message type.

        Args:
            msg: The message dictionary with a 'type' field
        """
        msg_type = msg.get("type", "unknown")
        logger.debug(f"[OptimizationServer] Processing message type: {msg_type}")

        handlers = {
            "add_node": self.handle_add_node,
            "similarity_search": self.handle_similarity_search,
            "cluster_nodes": self.handle_cluster_nodes,
            "optimize_graph": self.handle_optimize_graph,
            "shutdown": self.handle_shutdown,
        }

        handler = handlers.get(msg_type)
        if handler:
            handler(msg)
        else:
            logger.warning(f"[OptimizationServer] Unknown message type: {msg_type}")

    def connect_to_develop_server(self) -> bool:
        """
        Connect to the develop server as an optimization client.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.conn = socket.create_connection((HOST, PORT), timeout=5)

            # Send handshake identifying as optimization role
            handshake = {"type": "handshake", "role": "optimization"}
            send_json(self.conn, handshake)

            # Wait for session_id acknowledgment
            file_obj = self.conn.makefile("r")
            response_line = file_obj.readline()
            if response_line:
                response = json.loads(response_line.strip())
                if response.get("type") == "session_id":
                    logger.info("[OptimizationServer] Connected to develop server")
                    return True
                else:
                    logger.error(f"[OptimizationServer] Unexpected handshake response: {response}")

        except Exception as e:
            logger.error(f"[OptimizationServer] Failed to connect to develop server: {e}")

        return False

    def run(self) -> None:
        """Main loop: connect to develop server and process messages."""
        # Retry connection with backoff
        retry_count = 0
        max_retries = 5

        while retry_count < max_retries and self.running:
            if self.connect_to_develop_server():
                break
            retry_count += 1
            wait_time = min(2**retry_count, 30)
            logger.info(f"[OptimizationServer] Retrying connection in {wait_time} seconds...")
            time.sleep(wait_time)

        if not self.conn:
            logger.error("[OptimizationServer] Failed to connect after retries")
            return

        # Make socket non-blocking so we don't time out
        self.conn.setblocking(False)
        file_obj = self.conn.makefile("r")

        try:
            buffer = ""
            while self.running:
                try:
                    chunk = file_obj.readline()
                    if chunk:
                        msg = json.loads(chunk.strip())
                        self.process_message(msg)
                    else:
                        time.sleep(0.1)  # idle wait
                except json.JSONDecodeError:
                    continue
                except BlockingIOError:
                    time.sleep(0.1)  # idle wait
                    continue
                except Exception as e:
                    logger.error(f"[OptimizationServer] Error: {e}")
                    break

        finally:
            if self.conn:
                try:
                    self.conn.close()
                except:
                    pass
            logger.info("[OptimizationServer] Disconnected from develop server")


def main():
    """Main entry point for the optimization server."""
    logger.info("[OptimizationServer] Starting optimization server process...")
    logger.info(f"[OptimizationServer] Logs will be written to ~/.aco/optimization_server.log")
    client = OptimizationClient()
    try:
        client.run()
    except KeyboardInterrupt:
        logger.info("[OptimizationServer] Interrupted by user")
    except Exception as e:
        logger.error(f"[OptimizationServer] Fatal error: {e}")
        import traceback

        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
