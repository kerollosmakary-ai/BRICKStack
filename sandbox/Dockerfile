# Minimal sandbox image for code execution
# Build: docker build -t brickstack-sandbox ./sandbox
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    nodejs \
    npm \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    pytest \
    black \
    flake8

WORKDIR /workspace
RUN useradd -m -u 1000 sandbox && chown -R sandbox:sandbox /workspace
USER sandbox

CMD ["sleep", "infinity"]
