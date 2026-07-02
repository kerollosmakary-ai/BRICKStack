#!/bin/bash
# ════════════════════════════════════════════════════════════════════
#  Telegram Multi-Agent Bot Installer — LiteLLM Edition
#  Works with ANY provider: DeepSeek, Qwen, OpenAI, Ollama, local
# ════════════════════════════════════════════════════════════════════

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║     🧱 LiteLLM Telegram Bot — Installer                   ║"
    echo "║     Multi-Provider: DeepSeek, Qwen, OpenAI, Local, etc.     ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() { echo -e "${YELLOW}[STEP]${NC} $1"; }
print_ok() { echo -e "${GREEN}[OK]${NC} $1"; }

print_header

# ── Step 1: Dependencies ────────────────────────────────────────────
print_step "Installing Python packages..."
pkg update -y 2>/dev/null || true
pkg install -y python python-pip git curl 2>/dev/null || true
pip install --upgrade pip
pip install python-telegram-bot httpx pyyaml tenacity rich
print_ok "Python packages installed"

# ── Step 2: Setup Directories ─────────────────────────────────────
print_step "Setting up directories..."
INSTALL_DIR="${HOME}/telegram_agent"
mkdir -p "$INSTALL_DIR"
print_ok "Directory: $INSTALL_DIR"

# ── Step 3: Copy Bot ─────────────────────────────────────────────
print_step "Installing bot..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/bot.py" "$INSTALL_DIR/bot.py"
chmod +x "$INSTALL_DIR/bot.py"
print_ok "Bot installed"

# ── Step 4: Start Script ───────────────────────────────────────────
cat > "$INSTALL_DIR/start.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ Set TELEGRAM_BOT_TOKEN first:"
    echo "   export TELEGRAM_BOT_TOKEN='your_token'"
    exit 1
fi

echo "🤖 Starting Telegram Bot with LiteLLM..."
python3 bot.py
EOF
chmod +x "$INSTALL_DIR/start.sh"

# ── Step 5: Stop Script ───────────────────────────────────────────
cat > "$INSTALL_DIR/stop.sh" << 'EOF'
#!/bin/bash
pkill -f "python3 bot.py" 2>/dev/null
echo "✅ Bot stopped."
EOF
chmod +x "$INSTALL_DIR/stop.sh"

# ── Step 6: Environment Template ─────────────────────────────────
cat > "$INSTALL_DIR/env.sh" << 'EOF'
#!/bin/bash
# Telegram Bot Token (get from @BotFather)
export TELEGRAM_BOT_TOKEN="YOUR_TOKEN_HERE"

# Your Telegram User ID (get from @userinfobot)
export ADMIN_ID="YOUR_ID_HERE"

# Default LLM Model (any LiteLLM alias)
export LLM_MODEL="deepseek"
# Other options: local, qwen, gpt-4o, gpt-4o-mini, claude, gemini, groq-llama

# Provider API Keys (only needed for cloud providers)
export DEEPSEEK_API_KEY=""
export OPENAI_API_KEY=""
export QWEN_API_KEY=""
export ANTHROPIC_API_KEY=""
export GROQ_API_KEY=""
export GEMINI_API_KEY=""

# Local Ollama (for offline/local mode)
export OLLAMA_BASE_URL="http://localhost:11434"
EOF

# ── Instructions ─────────────────────────────────────────────────
print_ok "Installation complete!"

cat << 'INSTRUCTIONS'

═══════════════════════════════════════════════════════════════════
                    NEXT STEPS
═══════════════════════════════════════════════════════════════════

1. GET YOUR BOT TOKEN
   ────────────────────
   • Open Telegram → Search @BotFather
   • Type /newbot → Name your bot
   • Copy the token (e.g., 123456789:ABCdef...)

2. GET YOUR ADMIN ID
   ────────────────────
   • Search @userinfobot on Telegram
   • Copy your User ID (e.g., 123456789)

3. CONFIGURE ENVIRONMENT
   ──────────────────────
   Edit: nano ~/telegram_agent/env.sh

   Set:
     TELEGRAM_BOT_TOKEN="your_token"
     ADMIN_ID="your_id"
     LLM_MODEL="deepseek"   # or "local", "qwen", "gpt-4o", etc.

   Set API keys for your chosen provider:
     DEEPSEEK_API_KEY="sk-..."   (for deepseek)
     OPENAI_API_KEY="sk-..."       (for gpt-4o)
     QWEN_API_KEY="sk-..."         (for qwen)

4. ACTIVATE
   ──────────
   source ~/telegram_agent/env.sh

5. START THE BOT
   ──────────────
   ~/telegram_agent/start.sh

═══════════════════════════════════════════════════════════════════

PROVIDER QUICK REFERENCE
═══════════════════════════════════════════════════════════════════

┌──────────────┬──────────────────────────┬─────────────────────────┐
│ Model Alias  │ Provider                 │ Needs API Key?          │
├──────────────┼──────────────────────────┼─────────────────────────┤
│ deepseek     │ DeepSeek (China)         │ ✅ DEEPSEEK_API_KEY     │
│ local        │ Ollama (your phone)      │ ❌ No — runs offline    │
│ qwen         │ Qwen (Alibaba)           │ ✅ QWEN_API_KEY         │
│ gpt-4o       │ OpenAI GPT-4o            │ ✅ OPENAI_API_KEY       │
│ gpt-4o-mini  │ OpenAI (cheaper)         │ ✅ OPENAI_API_KEY       │
│ claude       │ Anthropic Claude 3.5     │ ✅ ANTHROPIC_API_KEY    │
│ gemini       │ Google Gemini            │ ✅ GEMINI_API_KEY       │
│ groq-llama   │ Groq (fast inference)    │ ✅ GROQ_API_KEY         │
└──────────────┴──────────────────────────┴─────────────────────────┘

SWITCHING MODELS IN TELEGRAM
═══════════════════════════════════════════════════════════════════

Send these commands to the bot:

  /model           → Show current model & picker
  /model deepseek  → Switch to DeepSeek
  /model local     → Switch to local Ollama (offline)
  /model qwen      → Switch to Qwen
  /model gpt-4o    → Switch to OpenAI GPT-4o
  /model claude    → Switch to Anthropic Claude


OFFLINE MODE (LOCAL ONLY)
═══════════════════════════════════════════════════════════════════

If you want to run completely offline (no API keys):

  1. Install Ollama:
     pkg install ollama 2>/dev/null || \
       curl -fsSL https://ollama.com/install.sh | sh

  2. Pull a small model:
     ollama pull qwen2.5-coder:3b

  3. Start Ollama:
     ollama serve &

  4. Set model to local:
     export LLM_MODEL="local"

  5. Start the bot

INSTRUCTIONS

echo -e "\n${GREEN}Bot installed in: ~/telegram_agent${NC}"
