#!/usr/bin/env python3

import socket
import json
import time
import uuid

# Test script to verify graph display is working with mock data
print("Testing graph display with mock data...")

# Connect to the develop server
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 5959))

# Send handshake
handshake = {
    "type": "hello",
    "role": "shim-control",
    "script": "test_graph_mock"
}
sock.sendall((json.dumps(handshake) + "\n").encode('utf-8'))

# Read session_id
file_obj = sock.makefile(mode='r')
session_line = file_obj.readline()
session_msg = json.loads(session_line.strip())
session_id = session_msg.get("session_id")
print(f"Connected with session_id: {session_id}")

# Send a mock node
node_id = str(uuid.uuid4())
node_msg = {
    "type": "addNode",
    "session_id": session_id,
    "node": {
        "id": node_id,
        "input": "Write a poem about debugging",
        "output": "Bugs are like shadows in the code,\nHiding in corners, ready to explode.\nBut with patience and a steady hand,\nWe'll find them all and make them stand.",
        "border_color": "#00c542",
        "label": "GPT-4 Poem",
        "codeLocation": "test_graph_mock.py:25",
        "model": "gpt-4o-mini",
        "api_type": "openai_v2",
    }
}
sock.sendall((json.dumps(node_msg) + "\n").encode('utf-8'))
print(f"Sent node: {node_id}")

# Send another mock node
node_id2 = str(uuid.uuid4())
node_msg2 = {
    "type": "addNode",
    "session_id": session_id,
    "node": {
        "id": node_id2,
        "input": "Explain recursion",
        "output": "Recursion is when a function calls itself. It's like a mirror reflecting a mirror - each reflection contains the same pattern, but smaller.",
        "border_color": "#ff6b35",
        "label": "GPT-4 Explanation",
        "codeLocation": "test_graph_mock.py:40",
        "model": "gpt-4o-mini",
        "api_type": "openai_v2",
    }
}
sock.sendall((json.dumps(node_msg2) + "\n").encode('utf-8'))
print(f"Sent node: {node_id2}")

# Send an edge between the nodes
edge_msg = {
    "type": "addEdge",
    "session_id": session_id,
    "edge": {
        "source": node_id,
        "target": node_id2
    }
}
sock.sendall((json.dumps(edge_msg) + "\n").encode('utf-8'))
print(f"Sent edge: {node_id} -> {node_id2}")

# Wait a bit for the UI to update
time.sleep(2)

# Send deregister
deregister_msg = {
    "type": "deregister",
    "session_id": session_id
}
sock.sendall((json.dumps(deregister_msg) + "\n").encode('utf-8'))

sock.close()
print("Test completed! Check the UI to see if the nodes and edge are displayed.") 