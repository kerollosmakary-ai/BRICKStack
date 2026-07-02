#!/bin/bash
# BRICKStack Secure Production Startup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "🔐 Environment loaded (secrets protected)"
fi

# Create log directory
mkdir -p /tmp/brickstack_logs
chmod 700 /tmp/brickstack_logs

# Create workspace
mkdir -p /tmp/brickstack_workspace
chmod 700 /tmp/brickstack_workspace

# Check secrets
if [ -f .env ]; then
    chmod 600 .env
fi

# Verify backend exists
if [ ! -f backend/main_secure.py ]; then
    echo "❌ Secure backend not found. Run hardening first."
    exit 1
fi

# Kill existing processes
pkill -f "uvicorn backend.main_secure" 2>/dev/null || true
pkill -f "telegram_bot.py" 2>/dev/null || true
sleep 1

# Start backend
echo "🚀 Starting secure backend on port ${API_PORT:-8000}..."
nohup python3 -m uvicorn backend.main_secure:app \
    --host "${API_HOST:-0.0.0.0}" \
    --port "${API_PORT:-8000}" \
    --workers 1 \
    > /tmp/brickstack_logs/backend.out.log \
    2> /tmp/brickstack_logs/backend.err.log &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/brickstack_backend.pid

# Wait for health
for i in {1..30}; do
    if curl -s "http://localhost:${API_PORT:-8000}/api/health" > /dev/null 2>&1; then
        echo "✅ Backend healthy (PID: $BACKEND_PID)"
        break
    fi
    sleep 1
    if [ $i -eq 30 ]; then
        echo "❌ Backend failed to start. Check /tmp/brickstack_logs/backend.err.log"
        exit 1
    fi
done

# Start Telegram bot (if token configured)
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    echo "🤖 Starting Telegram bot..."
    nohup python3 telegram_bot.py \
        > /tmp/brickstack_logs/telegram.out.log \
        2> /tmp/brickstack_logs/telegram.err.log &
    TELEGRAM_PID=$!
    echo $TELEGRAM_PID > /tmp/brickstack_telegram.pid
    echo "✅ Telegram bot started (PID: $TELEGRAM_PID)"
fi

echo ""
echo "🧱 BRICKStack is running securely:"
echo "   Backend:   http://localhost:${API_PORT:-8000}"
echo "   Health:    http://localhost:${API_PORT:-8000}/api/health"
echo "   Logs:      /tmp/brickstack_logs/"
echo "   PIDs:      /tmp/brickstack_*.pid"
echo ""
echo "🛑 To stop: ./stop.sh"
