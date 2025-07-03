import socket
import json
import time

HOST = '127.0.0.1'
PORT = 5959

# Connect and send handshake
s = socket.create_connection((HOST, PORT))
handshake = {"type": "hello", "role": "shim-runner", "script": "test_script.py"}
s.sendall((json.dumps(handshake) + "\n").encode("utf-8"))

# Print server's response (session_id)
print(s.recv(1024).decode())

# Send a test message
msg = {"type": "llm_log", "content": "Hello from shim!"}
s.sendall((json.dumps(msg) + "\n").encode("utf-8"))

# Keep the connection open to receive messages
while True:
    print(s.recv(1024).decode())
    time.sleep(1)