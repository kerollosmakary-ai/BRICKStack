# 🧱 BRICKStack — Production Deployment Guide

## Security Checklist

- [ ] `.env` has `chmod 600` (owner-only read)
- [ ] `JWT_SECRET` is a strong random string (not default)
- [ ] `LLM_API_KEY` is not committed to git
- [ ] `secrets/` directory has `chmod 700`
- [ ] WebSocket auth is enabled (`WS_REQUIRE_AUTH=true`)
- [ ] Rate limiting is active (30 req/min)
- [ ] HTTPS with valid SSL certificate
- [ ] Nginx reverse proxy configured
- [ ] Docker sandbox enabled for code execution
- [ ] Input validation active (max 10k prompt, 50k code)
- [ ] Logging enabled to `/var/log/brickstack/`

---

## Quick Start (Bare Metal / VPS)

### 1. Server Setup (Ubuntu 22.04+)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3-pip python3-venv nginx supervisor

# Create user (don't run as root)
sudo useradd -r -s /bin/false brickstack
sudo usermod -aG docker brickstack  # if using Docker sandbox
```

### 2. Clone & Harden

```bash
git clone https://github.com/kerollosmakary-ai/BRICKStack.git
cd BRICKStack
chmod 600 .env
bash harden.sh
```

### 3. Install Python Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
# Or minimal install:
pip install fastapi uvicorn httpx websockets
```

### 4. Start Secure Stack

```bash
./start_secure.sh
```

Check status:
```bash
./status.sh
```

---

## Docker Production (Recommended)

### 1. Install Docker & Compose

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Configure Secrets

Create `.env` with production values:

```bash
# Required
LLM_API_KEY=sk-your-deepseek-key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# Database (strong passwords!)
POSTGRES_USER=brickstack
POSTGRES_PASSWORD=$(openssl rand -hex 32)
POSTGRES_DB=brickstack
REDIS_PASSWORD=$(openssl rand -hex 32)

# Security
JWT_SECRET=$(openssl rand -hex 32)
WS_REQUIRE_AUTH=true
CORS_ORIGINS=https://your-domain.com

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your-bot-token
```

### 3. Deploy

```bash
cd deploy
docker-compose -f docker-compose.prod.yml up -d --build
```

### 4. SSL with Let's Encrypt

```bash
sudo apt install certbot
sudo certbot --nginx -d your-domain.com
```

Or use the certbot container in docker-compose (auto-renewal).

---

## Nginx Reverse Proxy (SSL)

Copy `deploy/nginx.conf` to `/etc/nginx/sites-available/brickstack`:

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/brickstack
sudo sed -i 's/your-domain.com/your-actual-domain.com/g' /etc/nginx/sites-available/brickstack
sudo ln -s /etc/nginx/sites-available/brickstack /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Supervisor (Auto-Restart)

Copy config:

```bash
sudo mkdir -p /var/log/brickstack
sudo cp deploy/supervisor.conf /etc/supervisor/conf.d/brickstack.conf
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start brickstack-backend
sudo supervisorctl start brickstack-telegram
```

---

## Telegram Bot Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create new bot, copy token
3. Add to `.env`: `TELEGRAM_BOT_TOKEN=your-token`
4. Start: `./start_secure.sh` or `docker-compose up telegram-bot`

The bot connects to your backend WebSocket and streams all agent outputs.

---

## Monitoring & Logs

### Check Service Status

```bash
./status.sh
```

### View Logs

```bash
# Backend
tail -f /tmp/brickstack_logs/backend.out.log
tail -f /tmp/brickstack_logs/backend.err.log

# Telegram
tail -f /tmp/brickstack_logs/telegram.out.log

# Nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Health Check

```bash
curl https://your-domain.com/api/health
# Expected: {"status": "ok", "llm_ready": true, ...}
```

---

## Security Hardening Details

### 1. Input Validation

All inputs are validated:
- **Prompts**: Max 10,000 chars, sanitized for null bytes
- **Code**: Max 50,000 chars, blacklist patterns checked
- **Task IDs**: Alphanumeric + hyphens only, max 64 chars
- **Path Traversal**: Blocked in file tree endpoint

### 2. Rate Limiting

- REST API: 30 requests/minute per IP
- WebSocket: 60 connections/minute per IP
- Configurable in `middleware/security.py`

### 3. Sandbox Execution

Code runs with:
- **Memory limit**: 128 MB
- **CPU limit**: 5 seconds
- **File size limit**: 1 MB
- **Process limit**: 10 subprocesses
- **Forbidden imports**: `os`, `subprocess`, `sys`, `socket`, etc.
- **No network access** (subprocess env stripped)

### 4. Authentication

- REST API: Bearer token via `Authorization` header
- WebSocket: Token via `?token=` query parameter (optional, enabled with `WS_REQUIRE_AUTH=true`)
- Token generation: `/api/token` endpoint (protect in production)

### 5. Secrets Management

For production, use one of:

**Option A: HashiCorp Vault**
```bash
vault kv put secret/brickstack llm_api_key=sk-... jwt_secret=...
```

**Option B: AWS Secrets Manager**
```bash
aws secretsmanager create-secret --name brickstack --secret-string file://.env
```

**Option C: Docker Secrets (Swarm)**
```bash
docker secret create brickstack_env .env
```

---

## Backup & Restore

### Database (PostgreSQL)

```bash
# Backup
docker exec -t brickstack-postgres-1 pg_dump -U brickstack brickstack > backup.sql

# Restore
docker exec -i brickstack-postgres-1 psql -U brickstack brickstack < backup.sql
```

### Workspace Files

```bash
tar czf workspace-backup.tar.gz /tmp/brickstack_workspace
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Backend won't start | Check `backend.err.log`, verify `.env` permissions |
| LLM not responding | Verify `LLM_API_KEY`, check DeepSeek balance |
| WebSocket disconnects | Check Nginx `proxy_read_timeout`, verify auth token |
| Telegram bot offline | Verify token, check `telegram.err.log`, ensure internet access |
| Code execution fails | Check sandbox limits, verify Python path |
| Rate limit errors | Adjust limits in `middleware/security.py` or Nginx config |

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   User      │────▶│   Nginx     │────▶│  FastAPI    │
│  (Browser)  │     │  (SSL/WS)   │     │  Backend    │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                       ┌──────────────┐    ┌────┴────┐
                       │   Telegram   │    │ Agents  │
                       │     Bot      │◄───┤Pipeline │
                       └──────────────┘    └────┬────┘
                                                  │
                       ┌──────────────┐    ┌────┴────┐
                       │   DeepSeek   │◄───┤  LLM    │
                       │    API       │    │ Client  │
                       └──────────────┘    └─────────┘
                       ┌──────────────┐
                       │   Sandbox    │
                       │  (subprocess)│
                       └──────────────┘
```

---

**Questions?** Open an issue at `github.com/kerollosmakary-ai/BRICKStack`
