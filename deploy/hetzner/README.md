# 🧱 BRICKStack Hetzner Optimized

**Production deployment for low-resource VPS (1-2 vCPU, 2-4GB RAM).**

Replaces heavy Docker stack with lightweight native services:
- **SQLite** instead of Postgres (saves ~200MB RAM)
- **No Redis** (saves ~50MB RAM)
- **Caddy** instead of Nginx (smaller binary, auto-HTTPS, simpler config)
- **Single Gunicorn worker** (2 workers on 4GB+ VPS)
- **Static files served by Caddy** (not Python)
- **External LLM only** (no local model overhead)

---

## 🚀 Quick Start (Fresh Hetzner VPS)

### 1. Create VPS
- Hetzner Cloud: **CX11** (1 vCPU, 2GB RAM, €3.29/mo) or **CPX11** (2 vCPU, 4GB RAM)
- OS: **Ubuntu 22.04/24.04** or **Debian 12**

### 2. Run Setup Script
```bash
# SSH into your server
ssh root@your-server-ip

# One-command setup
curl -fsSL https://raw.githubusercontent.com/kerollosmakary-ai/BRICKStack/main/deploy/hetzner/setup.sh | bash

# Or manually:
git clone https://github.com/kerollosmakary-ai/BRICKStack.git /var/www/brickstack
cd /var/www/brickstack/deploy/hetzner
bash setup.sh
```

### 3. Set API Key
```bash
sudo nano /var/www/brickstack/.env

# Set your provider key:
LLM_MODEL=deepseek
DEEPSEEK_API_KEY=sk-your-key-here

# Restart
sudo systemctl restart brickstack
```

### 4. Access
```
http://your-server-ip          → Web UI
http://your-server-ip/health   → Health check
http://your-server-ip/api/     → API docs
```

---

## 📊 Resource Usage

| Component | RAM | Notes |
|-----------|-----|-------|
| OS (Ubuntu) | ~400MB | Base system |
| Caddy | ~20MB | Reverse proxy + static files |
| FastAPI (1 worker) | ~150-300MB | Single Gunicorn worker |
| SQLite | ~0MB | Embedded, no separate process |
| **Total Active** | **~600-800MB** | Fits in 2GB VPS comfortably |
| **Free for Cache** | **~1.2GB** | Linux uses free RAM for disk cache |

### 2GB VPS (CX11)
```
┌─────────────────────────────┐
│  Ubuntu OS + Caddy  ~420MB  │
│  BRICKStack App     ~250MB  │
│  Buffer/Cache      ~1.2GB   │
│  Swap (2GB)              │  ← Safety net
└─────────────────────────────┘
         2GB Total RAM
```

### 4GB VPS (CPX11)
Can add:
- 2 Gunicorn workers
- Postgres (if you want)
- Redis (for caching)

---

## 🔧 Manual Setup (Without Script)

```bash
# 1. Update & swap
apt update && apt upgrade -y
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# 2. Install deps
apt install -y python3 python3-venv python3-pip git curl sqlite3 debian-keyring debian-archive-keyring apt-transport-https

# 3. Install Caddy
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy

# 4. Create user
useradd -r -m -s /bin/bash brickstack

# 5. Deploy app
git clone https://github.com/kerollosmakary-ai/BRICKStack.git /var/www/brickstack
chown -R brickstack:brickstack /var/www/brickstack

# 6. Python env
cd /var/www/brickstack
python3 -m venv venv
source venv/bin/activate
pip install -r deploy/hetzner/requirements.txt

# 7. Configure
cp deploy/hetzner/.env.example .env
nano .env  # Set your API key

# 8. Caddy config
cp deploy/hetzner/Caddyfile /etc/caddy/Caddyfile
systemctl restart caddy

# 9. Systemd services
cp deploy/hetzner/brickstack.service /etc/systemd/system/
cp deploy/hetzner/caddy.service /etc/systemd/system/caddy-brickstack.service
systemctl daemon-reload
systemctl enable brickstack caddy-brickstack
systemctl start brickstack caddy-brickstack

# 10. Firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

---

## 🛠️ Management Commands

```bash
# Status
sudo systemctl status brickstack
sudo systemctl status caddy-brickstack

# Logs
sudo journalctl -u brickstack -f          # Live logs
sudo journalctl -u brickstack -n 100        # Last 100 lines
sudo journalctl -u caddy-brickstack -f      # Caddy logs

# Restart
sudo systemctl restart brickstack
sudo systemctl restart caddy-brickstack

# Stop
sudo systemctl stop brickstack

# Update (pull latest code)
cd /var/www/brickstack
sudo -u brickstack git pull origin main
sudo systemctl restart brickstack
```

---

## 🔐 SSL / Domain Setup

### With Domain (Auto HTTPS via Caddy)

```bash
# Edit Caddyfile
sudo nano /etc/caddy/Caddyfile
```

Replace with:
```caddy
your-domain.com {
    encode gzip
    reverse_proxy /api/* localhost:8000
    reverse_proxy /ws localhost:8000
    reverse_proxy /health localhost:8000
    root * /var/www/brickstack/frontend
    try_files {path} /index.html
    file_server
    tls your-email@example.com
}
```

```bash
sudo systemctl restart caddy-brickstack
```

Caddy automatically provisions Let's Encrypt certificates. No certbot needed.

---

## 🔄 Updating

```bash
cd /var/www/brickstack
sudo -u brickstack git pull origin main
source venv/bin/activate
pip install -r deploy/hetzner/requirements.txt
sudo systemctl restart brickstack
```

---

## 🐛 Troubleshooting

### "Out of memory"
```bash
# Check swap
free -h

# Add more swap if needed
sudo swapoff /swapfile
sudo fallocate -l 4G /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Reduce workers to 1
sudo nano /var/www/brickstack/.env
# WORKERS=1
sudo systemctl restart brickstack
```

### "Caddy won't start"
```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo journalctl -u caddy-brickstack -n 50
```

### "BRICKStack won't start"
```bash
# Check env
sudo cat /var/www/brickstack/.env

# Check logs
sudo journalctl -u brickstack -n 50

# Test manually
sudo -u brickstack /var/www/brickstack/venv/bin/python -c "from backend.main_hetzner import app; print('OK')"
```

### "Port 80 already in use"
```bash
# Stop conflicting services
sudo systemctl stop nginx 2>/dev/null || true
sudo systemctl stop apache2 2>/dev/null || true
sudo systemctl restart caddy-brickstack
```

---

## 📈 Scaling Up

### 2GB → 4GB VPS

Edit `/var/www/brickstack/.env`:
```bash
WORKERS=2
```

Restart:
```bash
sudo systemctl restart brickstack
```

### 4GB+ VPS (Add Postgres + Redis)

Edit `deploy/hetzner/requirements.txt`:
```
asyncpg>=0.29.0
redis>=5.0.0
```

Edit `/var/www/brickstack/.env`:
```bash
DATABASE_URL=postgresql://user:pass@localhost/brickstack
REDIS_URL=redis://localhost:6379/0
WORKERS=2
```

Install Postgres + Redis:
```bash
sudo apt install -y postgresql redis-server
```

---

## 🎯 Comparison

| | Docker Stack | Hetzner Optimized |
|---|---|---|
| **RAM** | 1.5-2GB | **400-600MB** |
| **Processes** | 6+ (Docker, Postgres, Redis, Nginx, App) | **3** (Caddy, App, OS) |
| **Setup** | Complex | **One script** |
| **Updates** | Rebuild images | **Git pull + restart** |
| **SSL** | Manual certbot | **Caddy auto** |
| **Best for** | Development | **Production VPS** |

---

## 📄 Files

| File | Purpose |
|------|---------|
| `setup.sh` | One-command installer |
| `Caddyfile` | Caddy reverse proxy config |
| `brickstack.service` | Systemd unit for app |
| `caddy.service` | Systemd unit for Caddy |
| `requirements.txt` | Minimal Python deps |
| `.env.example` | Environment template |
| `start.sh` | Manual start script |
| `README.md` | This file |
| `../../backend/main_hetzner.py` | Optimized FastAPI backend |

---

## 🙏 Credits

- [Caddy](https://caddyserver.com/) — Auto-HTTPS web server
- [Hetzner](https://www.hetzner.com/cloud) — Cheap VPS
- [Gunicorn](https://gunicorn.org/) — Python WSGI server
- [Uvicorn](https://www.uvicorn.org/) — ASGI server

---

**Deploy a production AI coding assistant on a €3/month VPS.**
