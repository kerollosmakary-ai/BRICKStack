FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt* ./
RUN pip install --no-cache-dir fastapi uvicorn httpx websockets 2>/dev/null || true
RUN pip install --no-cache-dir asyncpg sqlalchemy 2>/dev/null || true

# Copy app code
COPY . .

EXPOSE 8000

# Default: run backend
CMD ["python3", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
