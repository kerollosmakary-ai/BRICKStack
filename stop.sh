#!/bin/bash
set -euo pipefail

echo "🛑 Stopping BRICKStack..."

for pidfile in /tmp/brickstack_*.pid; do
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        if kill -0 "$PID" 2>/dev/null; then
            echo "  Killing PID $PID ($(basename $pidfile .pid))"
            kill "$PID" 2>/dev/null || true
            sleep 1
            kill -9 "$PID" 2>/dev/null || true
        fi
        rm -f "$pidfile"
    fi
done

pkill -f "uvicorn backend.main_secure" 2>/dev/null || true
pkill -f "telegram_bot.py" 2>/dev/null || true

echo "✅ Stopped"
