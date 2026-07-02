# 🧱 Telegram Local AI Agent Bot

**Run a multi-agent AI coding assistant entirely on your Android phone.**

No cloud. No API keys. No data leaves your device. Works offline after setup.

---

## 📱 What You Get

A Telegram bot that runs on your phone (via Termux) with these AI agents:

| Agent | Icon | What It Does |
|-------|------|-------------|
| **Code** | 🧠 | Writes clean, efficient code with type hints |
| **Review** | 🔍 | Finds bugs, security issues, performance problems |
| **Explain** | 📖 | Breaks down code like a patient teacher |
| **Plan** | 📋 | Breaks tasks into actionable steps |
| **Debug** | 🐛 | Fixes errors and explains root causes |
| **Pipeline** | 🔄 | Runs all 4 agents in sequence on one task |

**Example:**
```
You (Pipeline mode): "Build a todo API in Flask"

Bot → 📋 Planner: Breaks it into 6 steps
Bot → 💻 Coder: Writes complete Flask API code
Bot → 🔍 Reviewer: Checks for SQL injection, missing auth
Bot → ✅ Summary: Stats + confirmation
```

All of this happens on your phone using a 3B parameter model.

---

## 🚀 Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **RAM** | 6 GB | 8+ GB |
| **Storage** | 4 GB free | 8 GB free |
| **OS** | Android 10+ | Android 12+ |
| **App** | Termux (F-Droid) | Termux + Termux:Boot |
| **Internet** | For setup only | For setup + model download |

> **Why 3B model?** A 3B parameter model uses ~2.2GB RAM (Q4_K_M quantized). On an 8GB phone, this leaves ~3GB for Android OS and apps — safe and stable. A 7B model would use ~4.5GB and likely cause crashes.

---

## 📦 Installation (One Command)

```bash
# 1. Install Termux from F-Droid (NOT Google Play)
#    https://f-droid.org/packages/com.termux/

# 2. In Termux, run:
termux-setup-storage
pkg update && pkg install -y git curl

# 3. Clone this repo
cd ~ && git clone https://github.com/kerollosmakary-ai/BRICKStack.git

# 4. Run the installer
cd BRICKStack/telegram_agent
bash install.sh

# 5. Follow the interactive prompts
#    (takes 10-15 minutes to download and compile)
```

---

## ⚙️ Configuration

### 1. Get Your Bot Token

1. Open Telegram → Search `@BotFather`
2. Type `/newbot`
3. Name it (e.g., `MyLocalAI_Bot`)
4. Copy the token: `123456789:ABCdefGHIjkl...`

### 2. Get Your Admin ID

1. Search `@userinfobot` on Telegram
2. It replies with your ID: `123456789`
3. Copy this number

### 3. Set Environment

```bash
# Edit the env file
nano ~/telegram_agent/env.sh

# Replace:
export TELEGRAM_BOT_TOKEN="123456789:YOUR_TOKEN_HERE"
export ADMIN_ID="123456789"

# Save and exit (Ctrl+X, Y, Enter)
# Activate:
source ~/telegram_agent/env.sh
```

> **Tip:** Add `source ~/telegram_agent/env.sh` to your `~/.bashrc` so it's always set.

---

## 🎮 Start Using

### Start Everything

```bash
# One command:
~/telegram_agent/start.sh

# This will:
# 1. Check if LLM server is running (start if not)
# 2. Start the Telegram bot
# 3. Keep running in foreground
```

### Use in Telegram

1. Open Telegram
2. Search your bot's name (from @BotFather)
3. Tap `/start`
4. Choose an agent mode or type directly

**Example conversation:**
```
You: 🧠 Code mode
You: Write a Python function to sort files by size

Bot: ```python
def sort_files_by_size(directory):
    from pathlib import Path
    return sorted(
        Path(directory).iterdir(),
        key=lambda p: p.stat().st_size,
        reverse=True
    )
```
```

### Pipeline Mode (Multi-Agent)

```
You: 🔄 Pipeline mode
You: Build a login system with JWT tokens

Bot [Planner]: 📋 1. Create user model 2. Add bcrypt hashing 3. JWT middleware...
Bot [Coder]: 💻 (complete Flask code)
Bot [Reviewer]: 🔍 Missing rate limiting, weak password policy...
Bot [Summary]: ✅ 4 agents, 12KB output, 15 seconds
```

---

## 🛑 Stop / Manage

| Action | Command |
|--------|---------|
| Stop everything | `~/telegram_agent/stop.sh` |
| Check status | `~/telegram_agent/status.sh` |
| Stop LLM from Telegram | Send `/stop_llm` to bot (admin) |
| Start LLM from Telegram | Send `/start_llm` to bot (admin) |
| Check RAM from Telegram | Send `/status` to bot |

**RAM Management is critical on 8GB phones:**
- The LLM server uses ~2.2GB RAM
- When you're not coding, send `/stop_llm` to free memory
- Your bot conversations and history are preserved
- Send `/start_llm` when ready to code again

---

## 📁 File Structure

```
~/telegram_agent/
├── bot.py              # Main bot (do not edit)
├── start.sh            # Start script
├── stop.sh             # Stop script
├── status.sh           # Status checker
├── env.sh              # Your config (edit this)
└── README.md           # This file

~/models/
└── qwen2.5-coder-3b.q4_k_m.gguf   # 3B model (2.5GB)

~/llama.cpp/
├── build/
│   └── bin/
│       └── llama-server             # LLM inference engine
└── ...
```

---

## 🔧 Manual Start (Advanced)

If you want to run components separately:

**Terminal 1 — LLM Server:**
```bash
~/llama.cpp/build/bin/llama-server \
    -m ~/models/qwen2.5-coder-3b.q4_k_m.gguf \
    -c 4096 \
    --port 8080 \
    -n 512
```

**Terminal 2 — Bot:**
```bash
source ~/telegram_agent/env.sh
cd ~/telegram_agent
python3 bot.py
```

---

## 🔌 Architecture

```
┌──────────────────────────────────────┐
│           Your Android Phone          │
│  ┌──────────┐      ┌──────────────┐  │
│  │ Telegram │──────▶│  llama.cpp  │  │
│  │   Bot    │◀──────│  (Qwen 3B)  │  │
│  │  (Python)│      │  localhost  │  │
│  └──────────┘      └──────────────┘  │
│         │                            │
│  ┌──────┴────────┐                   │
│  │  Agent Scripts │                   │
│  │  • Planner     │                   │
│  │  • Coder       │                   │
│  │  • Reviewer    │                   │
│  │  • Writer      │                   │
│  └────────────────┘                   │
└──────────────────────────────────────┘

Internet: Only for Telegram messages
AI Processing: 100% local on your phone
```

---

## ⚡ Performance

| Metric | Value |
|--------|-------|
| Model Size | 3 billion parameters |
| Quantization | Q4_K_M (4-bit) |
| Model File | ~2.5 GB |
| RAM Usage | ~2.2 GB when active |
| Inference Speed | 8-15 tokens/second (ARM CPU) |
| Time for 500 tokens | ~30-60 seconds |
| Quality | Good for code, logic, debugging |
| Offline | ✅ Fully offline after setup |

> **Note:** This is a 3B model. It won't match GPT-4 or Claude, but it's excellent for coding tasks, explanations, and debugging — especially for its size.

---

## 🛡️ Privacy & Security

| Feature | Status |
|---------|--------|
| Data leaves device | ❌ No |
| Requires internet for AI | ❌ No (after setup) |
| Requires Telegram API | ✅ Only for bot messages |
| Code stored on phone | ✅ Only in RAM (no persistence) |
| Conversation history | ✅ Per session (not saved to disk) |
| Admin commands | ✅ Protected by Telegram ID check |

---

## 🐛 Troubleshooting

### "Cannot connect to LLM server"
```bash
# Check if server is running
~/telegram_agent/status.sh

# If stopped, start it:
~/telegram_agent/start.sh

# Or from Telegram, send /start_llm (admin only)
```

### "Out of memory" / Phone crashes
```bash
# The 3B model should fit, but if not:
# 1. Close other apps
# 2. Use /stop_llm in Telegram when not coding
# 3. Consider a smaller model (1.5B) — edit env.sh
```

### "Model download failed"
```bash
# Manual download:
cd ~/models
wget https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf

# If huggingface is blocked, use:
# wget https://hf-mirror.com/... (same path)
```

### "Bot doesn't respond"
```bash
# Check if bot is running
pgrep -f "python3 bot.py"

# If not, restart
~/telegram_agent/start.sh
```

---

## 🔄 Auto-Start on Boot (Optional)

```bash
# Install Termux:Boot from F-Droid
# https://f-droid.org/packages/com.termux.boot/

mkdir -p ~/.termux/boot
ln -s ~/telegram_agent/start.sh ~/.termux/boot/

# Reboot your phone
# Bot will auto-start on boot
```

---

## 📝 License

Same as BRICKStack — MIT License.

---

## 🙏 Credits

- [llama.cpp](https://github.com/ggerganov/llama.cpp) — Fast local LLM inference
- [Qwen2.5-Coder](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct) — Coding model by Alibaba
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram integration

---

**Made for developers who want AI coding assistance without the cloud.**
