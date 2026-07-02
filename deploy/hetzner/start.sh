#!/bin/bash
# BRICKStack Hetzner — Manual Start Script

cd /var/www/brickstack
source venv/bin/activate

export $(grep -v '^#' .env | xargs)

echo "🧱 Starting BRICKStack Hetzner..."
echo "   Model: $LLM_MODEL"
echo "   Workers: ${WORKERS:-1}"

# Use Gunicorn for production (single worker for 2GB RAM)
exec gunicorn backend.main_hetzner:app \
    -w "${WORKERS:-1}" \
    -k uvicorn.workers.UvicornWorker \
    --bind "${API_HOST:-127.0.0.1}:${API_PORT:-8000}" \
    --timeout 120 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile - \
    --log-level info
