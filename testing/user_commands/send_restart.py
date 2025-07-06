import socket
import json
import time

HOST = '127.0.0.1'
PORT = 5959

# Connect to the server
sock = socket.create_connection((HOST, PORT), timeout=5)

# Send handshake
handshake = {"type": "hello", "role": "ui", "script": "restart_test"}
sock.sendall((json.dumps(handshake) + "\n").encode('utf-8'))

# Read the session message (which should include the list of PIDs)
file_obj = sock.makefile(mode='r')
session_line = file_obj.readline()
if session_line:
    try:
        session_msg = json.loads(session_line.strip())
        print(f"Session message: {session_msg}")
        
        # Get the list of available PIDs
        pids = session_msg.get("pids", [])
        print(f"Available PIDs: {pids}")
        
        if pids:
            # Send restart message to the first available PID
            target_pid = 23078 # pids[0]
            print(f"Sending restart to PID: {target_pid}")
            
            restart_msg = {"type": "restart", "process_id": target_pid}
            sock.sendall((json.dumps(restart_msg) + "\n").encode('utf-8'))
            print("Restart message sent!")
        else:
            print("No PIDs available for restart")
    except Exception as e:
        print(f"Error parsing session message: {e}")

sock.close() 