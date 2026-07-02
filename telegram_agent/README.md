# 🧱 LiteLLM Telegram Agent Bot

**Multi-provider AI coding assistant on Telegram.** Use DeepSeek, Qwen, OpenAI, Anthropic, Groq, or local models — all from one bot.

---

## 🌟 What Makes This Different

| Feature | Traditional Bot | This Bot |
|---------|----------------|----------|
| **Provider** | One hardcoded | **100+ via LiteLLM** |
| **Switching** | Restart code | **In-chat `/model` command** |
| **Offline** | Not possible | **Local Ollama mode** |
| **Fallback** | Manual | **Auto-retry + fallback** |
| **New provider** | Rebuild bot | **Add alias to config** |

---

## 🚀 Supported Providers

| Alias | Provider | Speed | Cost | Needs Key |
|-------|----------|-------|------|-----------|
| `deepseek` | DeepSeek (China) | Fast | $ | ✅ |
| `local` | Ollama (your phone) | Medium | Free | ❌ |
| `qwen` | Qwen 32B (Alibaba) | Fast | $ | ✅ |
| `gpt-4o` | OpenAI GPT-4o | Fast | $$ | ✅ |
| `gpt-4o-mini` | OpenAI (cheaper) | Fast | $ | ✅ |
| `claude` | Anthropic Claude 3.5 | Fast | $$ | ✅ |
| `gemini` | Google Gemini Pro | Fast | $ | ✅ |
| `groq-llama` | Groq (Llama 3.1 70B) | Very Fast | Free | ✅ |
| `groq-mixtral` | Groq (Mixtral 8x7B) | Very Fast | Free | ✅ |

---

## 📦 Installation (2 Minutes)

### 1. Install Termux
- Download from [F-Droid](https://f-droid.org/packages/com.termux/)
- **NOT** Google Play (outdated)

### 2. One-Command Install
```bash
termux-setup-storage
pkg update && pkg install -y git curl

cd ~ && git clone https://github.com/kerollosmakary-ai/BRICKStack.git
cd BRICKStack/telegram_agent
bash install.sh
```

### 3. Configure
```bash
nano ~/telegram_agent/env.sh

# Set these:
export TELEGRAM_BOT_TOKEN="123456789:YOUR_TOKEN_FROM_BOTFATHER"
export ADMIN_ID="123456789"
export LLM_MODEL="deepseek"  # or 'local', 'qwen', 'gpt-4o', etc.

# Set API key for your chosen provider:
export DEEPSEEK_API_KEY="sk-..."
# export OPENAI_API_KEY="sk-..."
# export QWEN_API_KEY="sk-..."
```

### 4. Start
```bash
source ~/telegram_agent/env.sh
~/telegram_agent/start.sh
```

---

## 🎮 Usage in Telegram

### Agent Modes

| Button | What It Does |
|--------|-------------|
| 🧠 **Code** | Writes code, includes type hints + error handling |
| 🔍 **Review** | Finds bugs, security issues, performance problems |
| 📖 **Explain** | Breaks down code like a patient teacher |
| 📋 **Plan** | Breaks tasks into numbered steps with complexity |
| 🐛 **Debug** | Fixes errors + adds test cases |
| 🔄 **Pipeline** | Runs all 4 agents in sequence |

### Switch Models (In-Chat)

Send these commands to your bot:

```
/model              → Show model picker
/model deepseek     → Switch to DeepSeek
/model local        → Switch to local Ollama (offline)
/model qwen         → Switch to Qwen 32B
/model gpt-4o       → Switch to OpenAI GPT-4o
/model claude       → Switch to Anthropic Claude
/model gemini       → Switch to Google Gemini
/model groq-llama   → Switch to Groq (fast, free)
```

### Example Conversations

**Coding:**
```
You: 🧠 Code mode
You: Write a JWT auth middleware in FastAPI

Bot: ```python
async def jwt_middleware(request: Request, call_next):
    token = request.headers.get("Authorization")
    ...
```
```

**Pipeline (Multi-Agent):**
```
You: 🔄 Pipeline mode
You: Build a URL shortener API

Bot [Planner]: 📋 1. Design schema 2. Create endpoints 3. Add caching...
Bot [Coder]: 💻 (complete FastAPI code)
Bot [Reviewer]: 🔍 Missing rate limiting, consider Redis...
Bot [Summary]: ✅ 4 agents, 15KB output, model: deepseek
```

**Switching:**
```
You: /model groq-llama
Bot: ✅ Model switched to groq/llama-3.1-70b-versatile
     Provider: GROQ
     Has Key: ✅

You: Write a Python script to parse JSON
Bot: (fast response from Groq)
```

---

## 🔌 Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Telegram   │────▶│   LiteLLM Client │────▶│   DeepSeek API   │
│   (Your Bot) │     │   (Unified)      │     │   (or any)       │
└──────────────┘     └──────────────────┘     └──────────────────┘
                            │
                            ├──▶ OpenAI API
                            ├──▶ Qwen API
                            ├──▶ Anthropic API
                            ├──▶ Groq API
                            ├──▶ Google Gemini
                            └──▶ Local Ollama ←──┐
                                                  │
                                        ┌────────┴────────┐
                                        │  Your Phone     │
                                        │  (Offline Mode) │
                                        └─────────────────┘
```

**The bot is just a thin Telegram wrapper around a unified LiteLLM client.**

---

## 🔧 Offline Mode (100% Local)

### 1. Install Ollama
```bash
pkg install ollama 2>/dev/null || \
  curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Pull a Model
```bash
# Small model for phones (2-3GB RAM)
ollama pull qwen2.5-coder:3b

# Or slightly larger (4-5GB RAM)
ollama pull qwen2.5-coder:7b
```

### 3. Start Ollama
```bash
ollama serve &
```

### 4. Configure Bot
```bash
export LLM_MODEL="local"
# No API key needed!
```

### 5. Start Bot
```bash
~/telegram_agent/start.sh
```

**Result:** All AI processing happens on your phone. Zero internet needed for inference. Only Telegram messages travel (encrypted).

---

## 📱 RAM Usage by Provider

| Provider | RAM Usage | Notes |
|----------|-----------|-------|
| **Cloud (DeepSeek, OpenAI, etc.)** | ~100 MB | Just the bot script |
| **Local Ollama (3B model)** | ~2.5 GB | Bot + LLM |
| **Local Ollama (7B model)** | ~4.5 GB | Bot + LLM (risky on 8GB) |

**Recommendation:**
- 8GB RAM → Use cloud providers or 3B local model
- 12GB+ RAM → Can use 7B local model comfortably
- Always close other apps when using local mode

---

## 🛡️ Security & Privacy

| Feature | Status |
|---------|--------|
| Data leaves device (cloud) | Only via API call to your chosen provider |
| Data leaves device (local) | ❌ No — 100% offline |
| API key stored | ❌ Not stored — read from env each time |
| Conversation history | ✅ Per session only (not saved) |
| Admin commands | ✅ Protected by Telegram ID |
| Telegram encryption | ✅ End-to-end |

---

## 🐛 Troubleshooting

### "No API key found"
```bash
# Set the right key for your model
export DEEPSEEK_API_KEY="sk-..."
export OPENAI_API_KEY="sk-..."
# etc.
```

### "Model switched but no response"
```bash
# Check if provider is accessible
python3 -c "import httpx; httpx.get('https://api.deepseek.com').raise_for_status()"
# Check your API key is valid
```

### "Local model not responding"
```bash
# Check Ollama is running
curl http://localhost:11434

# Pull model if not present
ollama pull qwen2.5-coder:3b
```

### "Out of memory (local mode)"
```bash
# Switch to a smaller model
ollama pull qwen2.5-coder:1.5b
# Or switch to cloud mode
# /model deepseek in Telegram
```

---

## 📝 Commands Reference

| Command | What It Does |
|---------|-------------|
| `/start` | Show main menu with agent buttons |
| `/model` | Show model picker or switch model |
| `/status` | Show current model, provider, key status |
| `/history` | Show last 6 conversation turns |
| `/clear` | Clear conversation history |
| `/help` | Show this help |

---

## 🔄 Auto-Start on Boot (Optional)

```bash
# Install Termux:Boot from F-Droid
mkdir -p ~/.termux/boot

# Create startup script
cat > ~/.termux/boot/start-bot.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
source ~/telegram_agent/env.sh
~/telegram_agent/start.sh
EOF

chmod +x ~/.termux/boot/start-bot.sh
# Reboot phone — bot starts automatically
```

---

## 🧪 Advanced: Custom Model Aliases

Edit `orchestrator/litellm_client.py` in the BRICKStack repo to add your own aliases:

```python
MODEL_ALIASES = {
    "my-custom": "ollama/my-custom-model",
    "azure-gpt": "azure/gpt-4",
    "cohere": "cohere/command-r",
    # ... add your own
}
```

Then use: `/model my-custom` in Telegram.

---

## 💡 Provider Tips

| Provider | Best For | Speed | Cost |
|----------|----------|-------|------|
| **DeepSeek** | Coding, reasoning | Fast | Very cheap |
| **Qwen** | Chinese + code | Fast | Cheap |
| **OpenAI** | General tasks | Fast | Expensive |
| **Claude** | Long documents, analysis | Fast | Expensive |
| **Groq** | Real-time, fast inference | Very fast | Free tier |
| **Gemini** | Multimodal, Google ecosystem | Fast | Cheap |
| **Local** | Privacy, offline, no cost | Medium | Free |

---

## 📊 Comparison with Other Bots

| Bot | Multi-Provider | Offline | Local Mode | Agent Pipeline | Cost |
|-----|---------------|---------|------------|---------------|------|
| ChatGPT | ❌ | ❌ | ❌ | ❌ | $$ |
| Claude | ❌ | ❌ | ❌ | ❌ | $$ |
| GitHub Copilot | ❌ | ❌ | ❌ | ❌ | $$ |
| LocalAI (generic) | ❌ | ✅ | ✅ | ❌ | Free |
| **This Bot** | ✅ **100+** | ✅ | ✅ | ✅ | **Free-$** |

---

## 🙏 Credits

- [LiteLLM](https://github.com/BerriAI/litellm) — Unified LLM interface
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram integration
- [Ollama](https://ollama.com/) — Local LLM inference
- [BRICKStack](https://github.com/kerollosmakary-ai/BRICKStack) — Core platform

---

**One bot, 100+ models, your choice of provider.**
