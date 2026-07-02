#!/bin/bash
echo "🧱 BRICKStack Status"
echo "===================="

for pidfile in /tmp/brickstack_*.pid; do
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        NAME=$(basename "$pidfile" .pid | sed 's/brickstack_//')
        if kill -0 "$PID" 2>/dev/null; then
            echo "✅ $NAME: running (PID $PID)"
        else
            echo "❌ $NAME: dead (PID $PID)"
        fi
    fi
done

# Check backend health
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    HEALTH=$(curl -s http://localhost:8000/api/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "unknown")
    echo "✅ Backend health: $HEALTH"
else
    echo "❌ Backend: not responding"
fi

# Log sizes
echo ""
echo "📋 Logs:"
for log in /tmp/brickstack_logs/*.log; do
    if [ -f "$log" ]; then
        SIZE=$(du -h "$log" | cut -f1)
        echo "   $SIZE $(basename $log)"
    fi
done
