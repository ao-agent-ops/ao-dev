#!/bin/bash
set -e

# Start backend Python server (in background)
echo "Starting Python backend on port 5959..."
python -m ao.cli.ao_server _serve &
PY_PID=$!

# Give backend time to start
sleep 2

# Start Node.js proxy (in foreground)
echo "Starting Node.js proxy on port 4000..."
cd src/user_interfaces/web_app
node server.js

# When proxy exits, kill backend
kill $PY_PID 2>/dev/null || true
