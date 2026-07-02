#!/usr/bin/env python3
"""
Telegram Multi-Agent Bot — LiteLLM Edition
Works with ANY provider: DeepSeek, Qwen, OpenAI, Anthropic, Groq, Ollama, local.

Setup:
    export TELEGRAM_BOT_TOKEN='your_token'
    export LLM_MODEL='deepseek'  # or 'local', 'qwen', 'gpt-4o', 'groq-llama', etc.
    python3 bot.py

Model Selection:
    /model          - Show available models and current selection
    /model deepseek - Switch to DeepSeek
    /model local    - Switch to local Ollama
    /model qwen     - Switch to Qwen (Alibaba)
    /model gpt-4o   - Switch to OpenAI GPT-4o

Architecture:
    Telegram Bot → LiteLLM Client → Any Provider (DeepSeek/Qwen/Ollama/etc.)
"""

import os
import sys
import logging
import time
import asyncio
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path

import httpx

# Setup logging
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger("telegram_bot")

# ── Configuration ───────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DEFAULT_MODEL = os.getenv("LLM_MODEL", "auto")
MAX_HISTORY = 10

# ── Agent Prompts ──────────────────────────────────────────────────
AGENTS = {
    "code": (
        "You are an expert software engineer. "
        "Write clean, efficient, well-documented code. "
        "Include type hints and error handling. "
        "Output the code block first, then a brief explanation."
    ),
    "review": (
        "You are a senior code reviewer. Check for:\n"
        "- Bugs and logic errors\n"
        "- Security vulnerabilities (injection, XSS, etc.)\n"
        "- Performance issues\n"
        "- Code style and readability\n"
        "- Missing edge case handling\n"
        "Provide severity ratings: 🔴 Critical / 🟡 Warning / 🟢 Suggestion"
    ),
    "explain": (
        "You are a patient teacher. Explain this code step by step:\n"
        "1. What it does overall\n"
        "2. How each part works\n"
        "3. Key concepts used\n"
        "Use simple analogies where helpful."
    ),
    "plan": (
        "You are a technical project manager. Break this task into steps:\n"
        "- Use numbered steps\n"
        "- Include file names and function names\n"
        "- Note dependencies needed\n"
        "- Estimate complexity (Low/Medium/High)"
    ),
    "debug": (
        "You are a debugging expert. Follow this process:\n"
        "1. Identify the root cause\n"
        "2. Explain why it fails\n"
        "3. Provide the corrected code\n"
        "4. Add a test case that catches this bug"
    ),
}

# ── Session Storage ────────────────────────────────────────────────
@dataclass
class UserSession:
    mode: str = "code"
    model: str = DEFAULT_MODEL
    history: List[Dict] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)

SESSIONS: Dict[int, UserSession] = defaultdict(UserSession)

# ── LiteLLM Client (Unified) ──────────────────────────────────────
# Import from BRICKStack orchestrator
sys.path.insert(0, str(Path(__file__).parent.parent))
from orchestrator.litellm_client import create_client, LiteLLMClient, MODEL_ALIASES

def get_llm_client(user_id: int) -> LiteLLMClient:
    """Get or create LiteLLM client for user."""
    session = SESSIONS[user_id]
    return create_client(model_name=session.model, temperature=0.3, max_tokens=4096)

# ── Telegram Bot ───────────────────────────────────────────────────
class AgentBot:
    def __init__(self, token: str):
        self.token = token
        self._check_deps()

    def _check_deps(self):
        try:
            from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
            from telegram.ext import (
                Application, CommandHandler, MessageHandler,
                CallbackQueryHandler, ContextTypes, filters
            )
        except ImportError:
            print("Installing python-telegram-bot...")
            os.system(f"{sys.executable} -m pip install python-telegram-bot --quiet")
            from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
            from telegram.ext import (
                Application, CommandHandler, MessageHandler,
                CallbackQueryHandler, ContextTypes, filters
            )

    def _keyboard(self):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🧠 Code", callback_data="code"),
                InlineKeyboardButton("🔍 Review", callback_data="review"),
            ],
            [
                InlineKeyboardButton("📖 Explain", callback_data="explain"),
                InlineKeyboardButton("📋 Plan", callback_data="plan"),
            ],
            [
                InlineKeyboardButton("🐛 Debug", callback_data="debug"),
                InlineKeyboardButton("🔄 Pipeline", callback_data="pipeline"),
            ],
            [
                InlineKeyboardButton("🤖 Model", callback_data="model_menu"),
                InlineKeyboardButton("📊 Status", callback_data="status"),
            ],
        ])

    def _model_keyboard(self, current_model: str):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        models = [
            ("🌐 DeepSeek", "deepseek"),
            ("🏠 Local", "local"),
            ("🇨🇳 Qwen", "qwen"),
            ("⚡ Groq", "groq-llama"),
            ("🤖 GPT-4o", "gpt-4o"),
            ("🧠 GPT-4o-mini", "gpt-4o-mini"),
            ("📖 Claude", "claude"),
            ("🔮 Gemini", "gemini"),
        ]
        buttons = []
        for label, alias in models:
            marker = " ✅" if alias == current_model else ""
            buttons.append(InlineKeyboardButton(f"{label}{marker}", callback_data=f"model:{alias}"))
        
        # Arrange in rows of 2
        rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
        rows.append([InlineKeyboardButton("◀️ Back", callback_data="back")])
        return InlineKeyboardMarkup(rows)

    async def start(self, update, context):
        user_id = update.effective_user.id
        session = SESSIONS[user_id]
        session.last_active = time.time()
        
        client = get_llm_client(user_id)
        info = client.get_info()

        await update.message.reply_text(
            f"🧱 *LiteLLM Agent Bot*\n\n"
            f"Model: `{info['model']}`\n"
            f"Provider: *{info['provider'].upper()}*\n"
            f"Device: *Android* 📱\n\n"
            f"Everything runs *locally* or via your chosen API.\n"
            f"Switch models with /model\n\n"
            f"Select an agent mode or type your request:",
            reply_markup=self._keyboard(),
            parse_mode="Markdown",
        )

    async def model_cmd(self, update, context):
        user_id = update.effective_user.id
        session = SESSIONS[user_id]
        
        if context.args and len(context.args) > 0:
            alias = context.args[0].lower()
            if alias in MODEL_ALIASES or alias == "auto":
                session.model = alias
                client = get_llm_client(user_id)
                info = client.get_info()
                await update.message.reply_text(
                    f"✅ Model switched to: *{info['model']}*\n"
                    f"Provider: *{info['provider'].upper()}*\n"
                    f"Has Key: {'✅' if info['has_api_key'] else '⚠️ No key'}\n\n"
                    f"Type /start to begin.",
                    parse_mode="Markdown",
                )
            else:
                available = "\n".join([f"• `{a}` → {MODEL_ALIASES[a]}" for a in sorted(MODEL_ALIASES.keys())[:20]])
                await update.message.reply_text(
                    f"❌ Unknown model: `{alias}`\n\n"
                    f"Available models:\n{available}\n\n"
                    f"Or use: /model auto (detects from env)",
                    parse_mode="Markdown",
                )
        else:
            client = get_llm_client(user_id)
            info = client.get_info()
            await update.message.reply_text(
                f"🤖 *Current Model:*\n\n"
                f"Alias: `{session.model}`\n"
                f"Resolved: `{info['model']}`\n"
                f"Provider: *{info['provider'].upper()}*\n\n"
                f"Select a model:",
                reply_markup=self._model_keyboard(session.model),
                parse_mode="Markdown",
            )

    async def help_cmd(self, update, context):
        text = (
            "🧱 *LiteLLM Agent Bot — Help*\n\n"
            "*Commands:*\n"
            "• /start — Show main menu\n"
            "• /model [name] — Show or switch models\n"
            "• /status — Check system + model status\n"
            "• /history — Show conversation history\n"
            "• /clear — Clear history\n\n"
            "*Agent Modes:*\n"
            "🧠 Code — Write code\n"
            "🔍 Review — Review code\n"
            "📖 Explain — Explain concepts\n"
            "📋 Plan — Break tasks into steps\n"
            "🐛 Debug — Fix errors\n"
            "🔄 Pipeline — Full multi-agent workflow\n\n"
            "*Model Switching:*\n"
            "• /model deepseek — DeepSeek API\n"
            "• /model local — Local Ollama (offline)\n"
            "• /model qwen — Qwen (Alibaba)\n"
            "• /model gpt-4o — OpenAI GPT-4o\n"
            "• /model groq-llama — Fast Groq inference\n"
            "• /model claude — Anthropic Claude\n"
            "• /model gemini — Google Gemini\n"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def status(self, update, context):
        user_id = update.effective_user.id
        session = SESSIONS[user_id]
        client = get_llm_client(user_id)
        info = client.get_info()
        
        text = (
            f"📊 *System Status*\n\n"
            f"🤖 Model: `{info['model']}`\n"
            f"🔧 Provider: *{info['provider'].upper()}*\n"
            f"🔑 API Key: {'✅ Set' if info['has_api_key'] else '⚠️ Not set'}\n"
            f"📡 Streaming: {'✅' if info['streaming'] else '❌'}\n"
            f"📱 Device: Android (Termux)\n\n"
            f"*Available Models:*\n"
        )
        for alias in sorted(MODEL_ALIASES.keys())[:15]:
            resolved = MODEL_ALIASES[alias]
            current = " ← current" if alias == session.model else ""
            text += f"• `{alias}` → {resolved}{current}\n"
        
        await update.message.reply_text(text, parse_mode="Markdown")

    async def history(self, update, context):
        user_id = update.effective_user.id
        session = SESSIONS[user_id]
        if not session.history:
            await update.message.reply_text("📭 No history yet.")
            return
        lines = [f"{i}. *{h['role']}*: {h['content'][:50]}..." for i, h in enumerate(session.history[-6:], 1)]
        await update.message.reply_text("📝 *Recent History*\n\n" + "\n".join(lines), parse_mode="Markdown")

    async def clear(self, update, context):
        user_id = update.effective_user.id
        SESSIONS[user_id].history.clear()
        await update.message.reply_text("🗑 History cleared.")

    async def button_handler(self, update, context):
        from telegram import Update
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        session = SESSIONS[user_id]

        if data == "status":
            await self.status(query, context)
            return
        if data == "help":
            await self.help_cmd(query, context)
            return
        if data == "model_menu":
            await query.edit_message_text(
                "🤖 *Select Model:*\n\n"
                "Choose a model to use:\n"
                "• 🏠 Local = offline, runs on your phone\n"
                "• 🌐 Cloud = requires API key, faster\n",
                reply_markup=self._model_keyboard(session.model),
                parse_mode="Markdown",
            )
            return
        if data == "back":
            await query.edit_message_text(
                f"🧱 *LiteLLM Agent Bot*\n\n"
                f"Model: `{session.model}`\n"
                f"Select an agent mode or type your request:",
                reply_markup=self._keyboard(),
                parse_mode="Markdown",
            )
            return
        if data.startswith("model:"):
            alias = data.split(":", 1)[1]
            session.model = alias
            client = get_llm_client(user_id)
            info = client.get_info()
            await query.edit_message_text(
                f"✅ Model switched to: *{info['model']}*\n"
                f"Provider: *{info['provider'].upper()}*\n"
                f"Has Key: {'✅' if info['has_api_key'] else '⚠️ No key'}\n\n"
                f"Select an agent mode:",
                reply_markup=self._keyboard(),
                parse_mode="Markdown",
            )
            return

        if data == "pipeline":
            session.mode = "pipeline"
            await query.edit_message_text(
                "🔄 *Multi-Agent Pipeline Mode*\n\n"
                "Send me a task and I'll run it through:\n"
                "1️⃣ Planner → 2️⃣ Coder → 3️⃣ Reviewer → 4️⃣ Writer\n\n"
                "Type your task below:",
                parse_mode="Markdown",
            )
        else:
            session.mode = data
            agent_name = {
                "code": "🧠 Code Writer",
                "review": "🔍 Code Reviewer",
                "explain": "📖 Explainer",
                "plan": "📋 Planner",
                "debug": "🐛 Debugger",
            }.get(data, "General")
            await query.edit_message_text(
                f"✅ Mode: *{agent_name}*\n\n"
                f"Model: `{session.model}`\n"
                f"Send me your request.",
                parse_mode="Markdown",
            )

    async def message_handler(self, update, context):
        user_id = update.effective_user.id
        text = update.message.text or ""
        if not text:
            return
        
        session = SESSIONS[user_id]
        session.last_active = time.time()

        if session.mode == "pipeline":
            await self._run_pipeline(update, text, user_id)
        else:
            await self._run_agent(update, text, session, user_id)

    async def _run_agent(self, update, text, session, user_id):
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        system = AGENTS.get(session.mode, AGENTS["code"])
        client = get_llm_client(user_id)
        
        messages = [{"role": "system", "content": system}]
        for h in session.history[-MAX_HISTORY:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": text})
        
        try:
            response = await client.complete(text, system=system)
        except Exception as e:
            logger.error(f"LLM error: {e}")
            response = f"❌ *Error:* `{str(e)[:500]}`\n\nTry switching model with /model"
        
        session.history.append({"role": "user", "content": text})
        session.history.append({"role": "assistant", "content": response})
        if len(session.history) > MAX_HISTORY * 2:
            session.history = session.history[-MAX_HISTORY * 2:]
        
        if len(response) > 4000:
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            await update.message.reply_text(response, parse_mode="Markdown")

    async def _run_pipeline(self, update, task, user_id):
        chat_id = update.effective_chat.id
        session = SESSIONS[user_id]
        client = get_llm_client(user_id)

        # Step 1: Plan
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        plan = await client.complete(f"Break this task into steps: {task}", system=AGENTS["plan"])
        await update.message.reply_text(f"📋 *Step 1: Planner*\n\n{plan[:3000]}", parse_mode="Markdown")

        # Step 2: Code
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        code = await client.complete(
            f"Task: {task}\n\nPlan:\n{plan}\n\nWrite the complete, runnable code.",
            system=AGENTS["code"]
        )
        await update.message.reply_text(f"💻 *Step 2: Coder*\n\n```python\n{code[:3000]}\n```", parse_mode="Markdown")

        # Step 3: Review
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        review = await client.complete(f"Review this code:\n\n{code}", system=AGENTS["review"])
        await update.message.reply_text(f"🔍 *Step 3: Reviewer*\n\n{review[:3000]}", parse_mode="Markdown")

        # Step 4: Summary
        summary = (
            f"✅ *Pipeline Complete!*\n\n"
            f"Task: {task[:100]}\n"
            f"Model: `{session.model}`\n"
            f"📋 Plan: {len(plan)} chars\n"
            f"💻 Code: {len(code)} chars\n"
            f"🔍 Review: {len(review)} chars\n\n"
            f"_All generated via {client.get_info()['provider'].upper()}_"
        )
        await update.message.reply_text(summary, parse_mode="Markdown")

    def run(self):
        from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
        
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("model", self.model_cmd))
        app.add_handler(CommandHandler("help", self.help_cmd))
        app.add_handler(CommandHandler("status", self.status))
        app.add_handler(CommandHandler("history", self.history))
        app.add_handler(CommandHandler("clear", self.clear))
        app.add_handler(CallbackQueryHandler(self.button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
        
        logger.info(f"Bot starting with model: {DEFAULT_MODEL}")
        logger.info(f"Available models: {len(MODEL_ALIASES)}")
        app.run_polling(drop_pending_updates=True)

# ── Main ───────────────────────────────────────────────────────────
def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
        print("=" * 60)
        print("ERROR: TELEGRAM_BOT_TOKEN not set!")
        print("=" * 60)
        print()
        print("1. Open Telegram and search for @BotFather")
        print("2. Type /newbot and follow instructions")
        print("3. Copy the token (looks like: 123456789:ABCdef...)")
        print("4. Set it:")
        print("   export TELEGRAM_BOT_TOKEN='your_token'")
        print("5. Optional: Set default model")
        print("   export LLM_MODEL='deepseek'  # or 'local', 'qwen', 'gpt-4o'")
        print()
        sys.exit(1)
    
    bot = AgentBot(TELEGRAM_BOT_TOKEN)
    bot.run()

if __name__ == "__main__":
    main()
