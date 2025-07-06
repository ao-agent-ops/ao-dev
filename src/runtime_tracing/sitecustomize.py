"""
Site customization module for agent-copilot runtime tracing.

This module is automatically imported by Python when it starts up.
It checks for the AGENT_COPILOT_ENABLE_TRACING environment variable
and applies monkey patches if tracing is enabled.
"""

import os
import socket
import json

def setup_tracing():
    """Set up runtime tracing if enabled via environment variable."""
    if not os.environ.get('AGENT_COPILOT_ENABLE_TRACING'):
        return
    
    # Get server connection details from environment
    host = os.environ.get('AGENT_COPILOT_SERVER_HOST', '127.0.0.1')
    port = int(os.environ.get('AGENT_COPILOT_SERVER_PORT', '5959'))
    
    # Try to connect to the develop server
    server_conn = None
    try:
        server_conn = socket.create_connection((host, port), timeout=5)
    except Exception:
        # If we can't connect, tracing is disabled
        return
    
    if server_conn:
        # Send handshake
        handshake = {
            "type": "hello", 
            "role": "shim-runner", 
            "script": os.path.basename(os.environ.get('_', 'unknown')),
            "process_id": os.getpid()
        }
        try:
            server_conn.sendall((json.dumps(handshake) + "\n").encode('utf-8'))
            # Read session_id from server
            file_obj = server_conn.makefile(mode='r')
            session_line = file_obj.readline()
            if session_line:
                try:
                    session_msg = json.loads(session_line.strip())
                    session_id = session_msg.get("session_id")
                except Exception:
                    pass
        except Exception:
            pass
        
        # Apply monkey patches
        try:
            from .monkey_patches import monkey_patch_llm_call
            monkey_patch_llm_call(server_conn)
        except Exception:
            pass

# Set up tracing when this module is imported
setup_tracing() 