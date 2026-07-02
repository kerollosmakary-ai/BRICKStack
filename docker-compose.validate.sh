#!/bin/bash
# Validate Docker Compose configuration without Docker installed

echo "🐳 Docker Compose Validation"
echo "============================"

# Check required files exist
files=(
  "docker-compose.yml"
  "deploy/Dockerfile"
  "deploy/nginx.simple.conf"
  "backend/main.py"
  "frontend/index.html"
  ".env"
)

for f in "${files[@]}"; do
  if [ -f "$f" ]; then
    echo "✅ $f"
  else
    echo "❌ MISSING: $f"
  fi
done

# Check env vars
echo ""
echo "📋 Required Environment Variables:"
if grep -q "LLM_API_KEY=" .env && ! grep -q "LLM_API_KEY=sk-your-key" .env; then
  echo "✅ LLM_API_KEY: set"
else
  echo "⚠️  LLM_API_KEY: needs your real key"
fi

if grep -q "TELEGRAM_BOT_TOKEN=" .env; then
  echo "✅ TELEGRAM_BOT_TOKEN: set (optional)"
else
  echo "ℹ️  TELEGRAM_BOT_TOKEN: not set (optional)"
fi

echo ""
echo "🚀 To start:"
echo "   docker-compose up --build -d"
echo ""
echo "🛑 To stop:"
echo "   docker-compose down"
echo ""
echo "📊 To view logs:"
echo "   docker-compose logs -f backend"
echo ""
echo "🌐 Access:"
echo "   Frontend: http://localhost"
echo "   API:      http://localhost:8000"
echo "   Health:   http://localhost:8000/api/health"
