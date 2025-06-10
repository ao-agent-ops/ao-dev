import socket
import sys
import os
import argparse
import json
import threading
import subprocess

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
            try:
                conn.sendall(data)
            except Exception:
                # Remove disconnected clients
                clients["shim_control"].remove(conn)

# Helper: handle a new client connection in a separate thread
def handle_client(conn: socket.socket, addr):
    global call_id_counter
    role = None
    try:
        # Expect a handshake message from the client identifying its role.
        file_obj = conn.makefile(mode='r')
        handshake_line = file_obj.readline()
        if not handshake_line:
            conn.close()
            return
        # Parse the handshake JSON (e.g., {"type": "hello", "role": "shim-control"}).
        handshake = json.loads(handshake_line.strip())
        role = handshake.get("role")
        # Register the connection under its role
        if role == "shim-control":
            clients["shim_control"].append(conn)
        elif role == "shim-runner":
            clients["shim_runner"].append(conn)
        elif role == "extension":
            clients["extension"].append(conn)
        # If an extension client just connected, send over any past call records for context
        if role == "extension":
            with threading.Lock():
                for record in calls:
                    try:
                        # Prefix the record with type "call" when sending to extension
                        ext_msg = {"type": "call", **record}
                        conn.sendall((json.dumps(ext_msg) + "\n").encode('utf-8'))
                    except Exception:
                        break  # stop if extension disconnects

        # Listen for incoming messages from this client
        for line in file_obj:
            msg = json.loads(line.strip())
            mtype = msg.get("type")
            if mtype == "call":
                # Shim runner is reporting an LLM call occurrence
                call_input = msg.get("input")
                call_output = msg.get("output")
                file_name = msg.get("file")
                line_no = msg.get("line")
                thread_id = msg.get("thread")
                task_id = msg.get("task")
                # Assign a unique ID to this call and record it
                with threading.Lock():
                    cid = call_id_counter
                    call_id_counter += 1
                    call_record = {
                        "id": cid,
                        "input": call_input,
                        "output": call_output,
                        "file": file_name,
                        "line": line_no,
                        "thread": thread_id,
                        "task": task_id
                    }
                    calls.append(call_record)
                # Forward the call record to any connected extension clients for visualization
                ext_data = json.dumps({"type": "call", **call_record}) + "\n"
                ext_data = ext_data.encode('utf-8')
                with threading.Lock():
                    for ext_conn in list(clients.get("extension", [])):
                        try:
                            ext_conn.sendall(ext_data)
                        except Exception:
                            clients["extension"].remove(ext_conn)
            elif mtype == "user_edit":
                # Extension is requesting an edit (LLM prompt modification)
                llm_id = msg.get("id")
                new_input = msg.get("new_input", "")
                user_edit(llm_id, new_input)  # signal the shim to restart with the new prompt
            elif mtype == "shutdown":
                # Gracefully shut down the server
                # Inform all clients and close their connections
                for conns in clients.values():
                    for c in conns:
                        try:
                            c.sendall((json.dumps({"type": "shutdown"}) + "\n").encode('utf-8'))
                        except Exception:
                            pass
                        try:
                            c.close()
                        except Exception:
                            pass
                clients["shim_control"].clear()
                clients["shim_runner"].clear()
                clients["extension"].clear()
                # Close server socket to break the accept loop and stop
                server_sock.close()
                break
    except Exception:
        # On error or disconnect, just proceed to cleanup
        pass
    finally:
        # Remove this connection from the appropriate list and close it
        if role == "shim-control" and conn in clients["shim_control"]:
            clients["shim_control"].remove(conn)
        if role == "shim-runner" and conn in clients["shim_runner"]:
            clients["shim_runner"].remove(conn)
        if role == "extension" and conn in clients["extension"]:
            clients["extension"].remove(conn)
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
            # Handle each connection in a new daemon thread
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except OSError:
        # This will be triggered when server_sock is closed (on shutdown)
        pass
    finally:
        server_sock.close()
        print("Develop server stopped.")

# CLI entry point
def main():
    parser = argparse.ArgumentParser(description="Development server for LLM call visualization")
    parser.add_argument('command', choices=['start', 'stop'], help="Start or stop the server")
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
        main()
