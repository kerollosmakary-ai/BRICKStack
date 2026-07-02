#!/bin/bash
# ════════════════════════════════════════════════════════════════════
#  Telegram Multi-Agent Bot Installer for Android (Termux)
#  Runs entirely on your phone — no cloud, no data leaves device
# ════════════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║     🧱 Telegram Local AI Agent Bot — Installer                ║"
    echo "║     For Android 8GB RAM (Termux)                              ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "${YELLOW}[STEP]${NC} $1"
}

print_ok() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ── Check Termux ────────────────────────────────────────────────────
print_header

if [ -z "$TERMUX_VERSION" ] && [ ! -d "/data/data/com.termux" ]; then
    echo "⚠️  This script is designed for Termux (Android)."
    echo "   It may work on other Linux systems but is optimized for Android."
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# ── Step 1: Install Dependencies ────────────────────────────────
print_step "Installing system packages..."
pkg update -y
pkg install -y python python-pip git curl wget cmake clang build-essential openssl
print_ok "System packages installed"

# ── Step 2: Install Python Libraries ────────────────────────────
print_step "Installing Python libraries..."
pip install --upgrade pip
pip install python-telegram-bot httpx psutil
print_ok "Python libraries installed"

# ── Step 3: Setup Directory ─────────────────────────────────────
print_step "Setting up directories..."
INSTALL_DIR="${HOME}/telegram_agent"
MODEL_DIR="${HOME}/models"
mkdir -p "$INSTALL_DIR" "$MODEL_DIR"
print_ok "Directories created: $INSTALL_DIR, $MODEL_DIR"

# ── Step 4: Download llama.cpp ──────────────────────────────────
print_step "Downloading llama.cpp (fast local inference)..."
if [ ! -d "${HOME}/llama.cpp" ]; then
    git clone --depth 1 https://github.com/ggerganov/llama.git "${HOME}/llama.cpp" 2>/dev/null || \
    git clone --depth 1 https://github.com/ggerganov/llama.cpp "${HOME}/llama.cpp"
    cd "${HOME}/llama.cpp"
    cmake -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --config Release -j$(nproc)
    print_ok "llama.cpp compiled successfully"
else
    print_ok "llama.cpp already exists (skipping)"
fi

# ── Step 5: Download Model ──────────────────────────────────────
print_step "Downloading Qwen2.5-Coder-3B model..."
MODEL_FILE="${MODEL_DIR}/qwen2.5-coder-3b.q4_k_m.gguf"

if [ -f "$MODEL_FILE" ]; then
    print_ok "Model already downloaded (skipping)"
else
    # Multiple mirrors in case one fails
    URLS=(
        "https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf"
        "https://hf-mirror.com/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf"
    )
    
    DOWNLOADED=0
    for URL in "${URLS[@]}"; do
        echo "Trying: $URL"
        if curl -L --progress-bar -o "$MODEL_FILE" "$URL" 2>/dev/null; then
            if [ -s "$MODEL_FILE" ]; then
                DOWNLOADED=1
                break
            fi
        fi
        echo "Failed, trying next mirror..."
    done
    
    if [ $DOWNLOADED -eq 0 ]; then
        print_error "Failed to download model automatically."
        echo "Manual download:"
        echo "  1. Visit https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF"
        echo "  2. Download qwen2.5-coder-3b-instruct-q4_k_m.gguf"
        echo "  3. Place it at: $MODEL_FILE"
        echo ""
        echo "Then re-run this installer."
        exit 1
    fi
    
    print_ok "Model downloaded: $(du -h "$MODEL_FILE" | cut -f1)"
fi

# ── Step 6: Copy Bot Files ──────────────────────────────────────
print_step "Installing bot files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/bot.py" "$INSTALL_DIR/bot.py"
chmod +x "$INSTALL_DIR/bot.py"
print_ok "Bot installed to $INSTALL_DIR"

# ── Step 7: Create Start Script ─────────────────────────────────
cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/bin/bash
# Start Telegram Bot with Local LLM

cd "$(dirname "$0")"

# Check environment
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ ERROR: TELEGRAM_BOT_TOKEN not set!"
    echo "   Get it from @BotFather on Telegram"
    echo "   Then run: export TELEGRAM_BOT_TOKEN='your_token'"
    exit 1
fi

# Check LLM server
if ! curl -s "http://localhost:8080" > /dev/null 2>&1; then
    echo "🚀 Starting LLM server..."
    nohup "${HOME}/llama.cpp/build/bin/llama-server" \
        -m "${HOME}/models/qwen2.5-coder-3b.q4_k_m.gguf" \
        -c 4096 --port 8080 \
        > "${HOME}/llama.log" 2>&1 &
    
    echo "   Waiting for LLM server to start..."
    for i in {1..30}; do
        if curl -s "http://localhost:8080" > /dev/null 2>&1; then
            echo "   ✅ LLM server ready!"
            break
        fi
        sleep 1
    done
else
    echo "✅ LLM server already running"
fi

# Start bot
echo "🤖 Starting Telegram Bot..."
python3 bot.py
EOF
chmod +x "$INSTALL_DIR/start.sh"

# ── Step 8: Create Stop Script ──────────────────────────────────
cat > "$INSTALL_DIR/stop.sh" << 'EOF'
#!/bin/bash
echo "🛑 Stopping services..."
pkill -f "llama-server" 2>/dev/null
pkill -f "python3 bot.py" 2>/dev/null
echo "✅ Stopped."
EOF
chmod +x "$INSTALL_DIR/stop.sh"

# ── Step 9: Create Status Script ──────────────────────────────
cat > "$INSTALL_DIR/status.sh" << 'EOF'
#!/bin/bash
echo "📊 Telegram Agent Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━"

# Check LLM
if pgrep -f "llama-server" > /dev/null; then
    echo "🤖 LLM Server:  ✅ Running"
else
    echo "🤖 LLM Server:  ❌ Stopped"
fi

# Check Bot
if pgrep -f "python3 bot.py" > /dev/null; then
    echo "🤖 Telegram Bot: ✅ Running"
else
    echo "🤖 Telegram Bot: ❌ Stopped"
fi

# Memory
if command -v python3 &> /dev/null; then
    python3 -c "
import psutil
m = psutil.virtual_memory()
print(f'💾 RAM: {m.used/1024**3:.1f}GB / {m.total/1024**3:.1f}GB ({m.percent}%)')
"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━"
EOF
chmod +x "$INSTALL_DIR/status.sh"

# ── Step 10: Environment Setup ──────────────────────────────────
cat > "$INSTALL_DIR/env.sh" << EOF
#!/bin/bash
# Source this file before running: source env.sh
export TELEGRAM_BOT_TOKEN="YOUR_TOKEN_HERE"
export ADMIN_ID="YOUR_TELEGRAM_ID"
export LLM_URL="http://localhost:8080/v1/chat/completions"
export LLM_MODEL="qwen2.5-coder-3b"
EOF

# ── Step 11: Instructions ─────────────────────────────────────
print_ok "Installation complete!"

echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    NEXT STEPS                                 ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"

cat << 'INSTRUCTIONS'

1. GET YOUR BOT TOKEN
   ──────────────────
   • Open Telegram, search for @BotFather
   • Type /newbot
   • Name your bot (e.g., "MyLocalAI")
   • Copy the token (looks like: 123456789:ABCdef...)

2. GET YOUR TELEGRAM ID (for admin commands)
   ──────────────────────────────────────────
   • Search for @userinfobot on Telegram
   • It will reply with your User ID (e.g., 123456789)
   • Copy this number

3. SET ENVIRONMENT
   ─────────────────
   Edit the env file:
     nano ~/telegram_agent/env.sh
   
   Replace:
     TELEGRAM_BOT_TOKEN="YOUR_TOKEN_HERE"
     ADMIN_ID="YOUR_TELEGRAM_ID"
   
   Then activate:
     source ~/telegram_agent/env.sh

4. START EVERYTHING
   ──────────────────
   One command:
     ~/telegram_agent/start.sh

   Or manually:
     # Terminal 1 — LLM Server
     ~/llama.cpp/build/bin/llama-server \
       -m ~/models/qwen2.5-coder-3b.q4_k_m.gguf \
       -c 4096 --port 8080
     
     # Terminal 2 — Bot (in another session)
     source ~/telegram_agent/env.sh
     cd ~/telegram_agent && python3 bot.py

5. USE YOUR BOT
   ─────────────
   • Open Telegram, search for your bot name
   • Tap /start
   • Choose an agent mode or type directly
   • Available modes:
     🧠 Code — Write code
     🔍 Review — Review code
     📖 Explain — Explain concepts
     📋 Plan — Break tasks into steps
     🐛 Debug — Fix errors
     🔄 Pipeline — Full multi-agent workflow

6. MANAGE RAM (Important for 8GB phones!)
   ──────────────────────────────────────
   • Use /stop_llm in Telegram to free RAM when done
   • Use /start_llm to restart the LLM server
   • Check /status anytime to see RAM usage

7. COMMANDS
   ─────────
   /start    — Show menu
   /status   — Check system status
   /history  — Show conversation history
   /clear    — Clear history
   /help     — Show help

   Admin only:
   /start_llm — Start LLM server
   /stop_llm  — Stop LLM server (free RAM)

8. SHORTCUTS
   ──────────
   Stop everything:
     ~/telegram_agent/stop.sh
   
   Check status:
     ~/telegram_agent/status.sh

INSTRUCTIONS

echo -e "\n${GREEN}Your bot is installed in: ~/telegram_agent${NC}"
echo -e "${GREEN}Model is at: ~/models/qwen2.5-coder-3b.q4_k_m.gguf${NC}"
echo -e "\n${YELLOW}RAM Usage Estimate:${NC}"
echo "  • Android OS: ~3GB"
echo "  • LLM Server (3B model): ~2.2GB"
echo "  • Bot Script: ~100MB"
echo "  • Available for apps: ~2.7GB"
echo ""
echo "  ${YELLOW}Tip: Use /stop_llm when not coding to free 2GB instantly${NC}"
