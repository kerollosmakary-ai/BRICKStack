#!/bin/bash
# ════════════════════════════════════════════════════════════════════
#  BRICKStack Hetzner Optimized Setup
#  One-command deployment for low-resource VPS (1-2 vCPU, 2-4GB RAM)
# ════════════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║     🧱 BRICKStack Hetzner Optimized Setup                   ║"
    echo "║     For 1-2 vCPU, 2-4GB RAM VPS                             ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() { echo -e "${YELLOW}[STEP]${NC} $1"; }
print_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header

# ── Configuration ───────────────────────────────────────────────────
INSTALL_DIR="${INSTALL_DIR:-/var/www/brickstack}"
APP_USER="${APP_USER:-brickstack}"
DOMAIN="${DOMAIN:-}"  # Set via env: export DOMAIN=your-domain.com

# ── Step 1: System Update ─────────────────────────────────────────
print_step "Updating system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
print_ok "System updated"

# ── Step 2: Create Swap (Critical for 2GB RAM) ────────────────────
print_step "Configuring swap (essential for 2GB RAM)..."
if ! swapon -s | grep -q "/swapfile"; then
    if [ ! -f /swapfile ]; then
        fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
        chmod 600 /swapfile
        mkswap /swapfile
        swapon /swapfile
        echo '/swapfile none swap sw 0 0' >> /etc/fstab
        print_ok "2GB swap created"
    else
        swapon /swapfile 2>/dev/null || true
        print_ok "Swap already exists"
    fi
else
    print_ok "Swap already active"
fi

# ── Step 3: Install Dependencies ──────────────────────────────────
print_step "Installing dependencies (Python, Caddy, etc.)..."
apt-get install -y -qq \
    python3 python3-venv python3-pip \
    git curl wget \
    sqlite3 \
    debian-keyring debian-archive-keyring apt-transport-https
print_ok "Dependencies installed"

# ── Step 4: Install Caddy (lighter than Nginx) ──────────────────
print_step "Installing Caddy web server..."
if ! command -v caddy &> /dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy
    print_ok "Caddy installed"
else
    print_ok "Caddy already installed"
fi

# ── Step 5: Create App User ──────────────────────────────────────
print_step "Creating app user ($APP_USER)..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -m -s /bin/bash "$APP_USER"
    print_ok "User $APP_USER created"
else
    print_ok "User $APP_USER exists"
fi

# ── Step 6: Clone / Deploy BRICKStack ───────────────────────────
print_step "Deploying BRICKStack to $INSTALL_DIR..."
if [ -d "$INSTALL_DIR/.git" ]; then
    cd "$INSTALL_DIR"
    git pull origin main
    print_ok "Updated existing repo"
else
    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
    fi
    git clone https://github.com/kerollosmakary-ai/BRICKStack.git "$INSTALL_DIR"
    print_ok "Cloned BRICKStack repo"
fi

chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"

# ── Step 7: Python Virtual Environment ────────────────────────────
print_step "Setting up Python virtual environment..."
cd "$INSTALL_DIR"
if [ ! -d venv ]; then
    python3 -m venv venv
    print_ok "Virtual environment created"
else
    print_ok "Virtual environment exists"
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r deploy/hetzner/requirements.txt
print_ok "Python packages installed"

# ── Step 8: Configure Environment ─────────────────────────────────
print_step "Configuring environment..."
ENV_FILE="$INSTALL_DIR/.env"
if [ ! -f "$ENV_FILE" ] || [ ! -s "$ENV_FILE" ]; then
    cat > "$ENV_FILE" << EOF
# BRICKStack Hetzner Configuration
LLM_MODEL=deepseek
DEEPSEEK_API_KEY=sk-your-key-here
API_HOST=127.0.0.1
API_PORT=8000
WORKERS=1
EOF
    chown "$APP_USER:$APP_USER" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    print_ok "Environment file created (edit $ENV_FILE with your API key)"
else
    print_ok "Environment file exists (edit $ENV_FILE if needed)"
fi

# ── Step 9: Create Data Directory ──────────────────────────────────
mkdir -p "$INSTALL_DIR/data"
chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR/data"
chmod 750 "$INSTALL_DIR/data"
print_ok "Data directory ready"

# ── Step 10: Configure Caddy ──────────────────────────────────────
print_step "Configuring Caddy..."
CADDY_CONF="/etc/caddy/Caddyfile"
mkdir -p /etc/caddy

if [ -n "$DOMAIN" ]; then
    # Production: with domain + HTTPS
    cat > "$CADDY_CONF" << EOF
$DOMAIN {
    encode gzip
    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        X-XSS-Protection "1; mode=block"
    }
    handle_path /api/* {
        reverse_proxy localhost:8000
    }
    handle_path /ws {
        reverse_proxy localhost:8000
    }
    handle_path /health {
        reverse_proxy localhost:8000
    }
    handle {
        root * $INSTALL_DIR/frontend
        try_files {path} /index.html
        file_server
    }
}
EOF
else
    # Development: IP only, no HTTPS
    cp "$INSTALL_DIR/deploy/hetzner/Caddyfile" "$CADDY_CONF"
fi

chown caddy:caddy "$CADDY_CONF" 2>/dev/null || true
chmod 644 "$CADDY_CONF"
print_ok "Caddy configured"

# ── Step 11: Systemd Services ─────────────────────────────────────
print_step "Installing systemd services..."

# Caddy service
cp "$INSTALL_DIR/deploy/hetzner/caddy.service" /etc/systemd/system/caddy-brickstack.service
systemctl daemon-reload

# BRICKStack service
cp "$INSTALL_DIR/deploy/hetzner/brickstack.service" /etc/systemd/system/brickstack.service

# Update service with correct paths
sed -i "s|/var/www/brickstack|$INSTALL_DIR|g" /etc/systemd/system/brickstack.service
systemctl daemon-reload
print_ok "Systemd services installed"

# ── Step 12: Start Services ───────────────────────────────────────
print_step "Starting services..."

systemctl enable caddy-brickstack
systemctl enable brickstack

# Start Caddy first
systemctl restart caddy-brickstack || systemctl restart caddy
print_ok "Caddy started"

# Start BRICKStack
systemctl restart brickstack
sleep 2

# Check if running
if systemctl is-active --quiet brickstack; then
    print_ok "BRICKStack is running"
else
    print_error "BRICKStack failed to start. Check: journalctl -u brickstack -n 50"
    exit 1
fi

# ── Step 13: Firewall (optional) ───────────────────────────────────
print_step "Configuring firewall..."
if command -v ufw &> /dev/null; then
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
    print_ok "UFW firewall enabled"
else
    apt-get install -y -qq ufw
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw --force enable
    print_ok "UFW installed and enabled"
fi

# ── Step 14: Final Info ───────────────────────────────────────────
IP=$(hostname -I | awk '{print $1}')
print_ok "Setup complete!"

cat << "INFO"

═══════════════════════════════════════════════════════════════════
                    BRICKStack Hetzner — READY
═══════════════════════════════════════════════════════════════════

🌐 Access URLs:
INFO

if [ -n "$DOMAIN" ]; then
    echo "   https://$DOMAIN     (Web UI)"
    echo "   https://$DOMAIN/api/  (API)"
    echo "   https://$DOMAIN/health (Health check)"
else
    echo "   http://$IP            (Web UI)"
    echo "   http://$IP/health     (Health check)"
fi

cat << "INFO"

📁 Installation: $INSTALL_DIR
👤 User: $APP_USER
💾 Database: $INSTALL_DIR/data/brickstack.db (SQLite)
⚙️  Config: $INSTALL_DIR/.env

🛠️  Management Commands:
   sudo systemctl status brickstack
   sudo systemctl restart brickstack
   sudo systemctl stop brickstack
   sudo journalctl -u brickstack -f        (live logs)
   sudo journalctl -u brickstack -n 100    (last 100 lines)

   sudo systemctl status caddy-brickstack
   sudo systemctl restart caddy-brickstack

📊 Resource Usage:
   Caddy:     ~20MB RAM
   FastAPI:   ~150-300MB RAM (1 worker)
   SQLite:    ~0MB (embedded)
   Total:     ~250-350MB + OS (~400MB)
   
   On 2GB VPS: ~1.2GB free for cache/buffer

⚠️  IMPORTANT: Set your API key!
   sudo nano $INSTALL_DIR/.env
   # Set DEEPSEEK_API_KEY or your provider key
   sudo systemctl restart brickstack

═══════════════════════════════════════════════════════════════════
INFO
