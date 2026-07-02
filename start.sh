#!/bin/bash
# BRICKStack Studio — Quick Start Script

set -e

echo "🧱 BRICKStack Studio — Starting up..."

# Check if we're in Docker or local
if [ -f /.dockerenv ]; then
    echo "Running inside Docker container"
else
    echo "Local mode detected (no Docker)"
fi

# Check Python
python3 --version || { echo "Python 3 not found"; exit 1; }

# Check if dependencies are installed
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r backend/requirements.txt
fi

# Set default env if not present
export API_HOST=${API_HOST:-0.0.0.0}
export API_PORT=${API_PORT:-8000}
export JWT_SECRET=${JWT_SECRET:-dev-secret-change-me}
export LLM_API_KEY=${LLM_API_KEY:-mock-key}
export LLM_BASE_URL=${LLM_BASE_URL:-http://localhost:8000}
export LLM_MODEL=${LLM_MODEL:-mock}
export DATABASE_URL=${DATABASE_URL:-sqlite:///:memory:}
export REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}
export SANDBOX_IMAGE=${SANDBOX_IMAGE:-brickstack-sandbox}
export SANDBOX_TIMEOUT=${SANDBOX_TIMEOUT:-120}

echo "🚀 Starting server on http://$API_HOST:$API_PORT"
echo "📁 Frontend: http://$API_HOST:$API_PORT"
echo "🔌 WebSocket: ws://$API_HOST:$API_PORT/ws"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 -m uvicorn backend.main:app --host $API_HOST --port $API_PORT --reload
