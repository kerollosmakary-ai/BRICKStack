#!/bin/bash
# BRICKStack Production Hardening Script

set -euo pipefail

echo "🔒 Hardening BRICKStack for production..."

# ── 1. Secret Permissions ─────────────────────────────────────
chmod 600 .env
chown $(whoami):$(whoami) .env
echo "✅ .env permissions set to 600 (owner-only read)"

# ── 2. Create secrets directory ─────────────────────────────────
mkdir -p secrets
chmod 700 secrets

# ── 3. Generate strong JWT secret if not set ────────────────────
if grep -q "dev-secret-change-me" .env; then
    NEW_SECRET=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-zA-Z0-9' | head -c 64)
    sed -i "s/dev-secret-change-me-in-production-2024/$NEW_SECRET/" .env
    echo "✅ Generated new JWT secret"
fi

# ── 4. Create restricted workspace ──────────────────────────────
mkdir -p /tmp/brickstack_workspace
chmod 700 /tmp/brickstack_workspace
echo "✅ Sandbox workspace created and restricted"

# ── 5. Verify no secrets in git ─────────────────────────────────
if [ -d .git ]; then
    if ! grep -q ".env" .gitignore 2>/dev/null; then
        echo ".env" >> .gitignore
        echo "secrets/" >> .gitignore
        echo "*.pem" >> .gitignore
        echo "*.key" >> .gitignore
        echo "✅ Added secrets to .gitignore"
    fi
fi

echo "🔒 Hardening complete. Review .env and secrets/ directory."
