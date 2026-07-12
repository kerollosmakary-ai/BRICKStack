#!/bin/bash
# Start the bridge + terminal agent
cd "$(dirname "$0")"

# Start the Python bridge in background
python3 connector.py &
BRIDGE_PID=$!
echo "🔗 Bridge started (PID $BRIDGE_PID)"

# Start the Node.js server
echo "🧱 Starting Brick Terminal Agent..."
node server.js
