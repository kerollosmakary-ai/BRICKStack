#!/usr/bin/env python3
"""
Telegram Multi-Agent Bot for Android (Termux)
Runs entirely on your phone — no cloud required.

Features:
- Single agent modes: /code, /review, /explain, /plan, /debug
- Multi-agent pipeline: /pipeline
- Local LLM control: /start_llm, /stop_llm
- System status: /status
- Conversation history per user
- Admin-only server controls

Requirements:
- Termux (Android)
- python-telegram-bot
- httpx
- psutil
- A running llama.cpp server (or any OpenAI-compatible local endpoint)
"""

import os
import sys
import json
import asyncio
import logging
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from collections import defaultdict
import subprocess

import httpx

# ── Configuration ──────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
LLM_URL = os.getenv("LLM_URL", "http://localhost:8080/v1/chat/completions")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder-3b")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MAX_HISTORY = 10

# ── Agent System Prompts ────────────────────────────────────────────
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

# ── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("agent_bot")

# ── Data Storage ────────────────────────────────────────────────────
@dataclass
class UserSession:
    mode: str = "code"
    history: List[Dict] = field(default_factory=list)
    last_active: float = field(default_factory=time.time)

SESSIONS: Dict[int, UserSession] = defaultdict(UserSession)

# ── LLM Client ──────────────────────────────────────────────────────
class LLMClient:
    def __init__(self, url: str, model: str, timeout: int = 120):
        self.url = url
        self.model = model
        self.timeout = timeout

    async def chat(self, system: str, user: str, history: List[Dict] = None) -> str:
        messages = [{"role": "system", "content": system}]
        if history:
            for h in history[-MAX_HISTORY:]:
                messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user})

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(self.url, json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 2048,
                    "stream": False,
                })
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
        except httpx.ConnectError:
            logger.error("Cannot connect to LLM server")
            return "❌ *LLM server is offline.*\n\nUse /start_llm to start it."
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return f"❌ Error: {str(e)[:500]}"

# ── Bot Handlers ────────────────────────────────────────────────────
class AgentBot:
    def __init__(self, token: str, llm: LLMClient):
        self.token = token
        self.llm = llm
        self._check_deps()

    def _check_deps(self):
        try:
            from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
            from telegram.ext import (
                Application, CommandHandler, MessageHandler,
                CallbackQueryHandler, ContextTypes, filters
            )
            self.tg = True
        except ImportError:
            logger.error("python-telegram-bot not installed.")
            logger.info("Run: pip install python-telegram-bot")
            sys.exit(1)

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
                InlineKeyboardButton("📊 Status", callback_data="status"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
        ])

    async def start(self, update, context):
        from telegram import Update
        user_id = update.effective_user.id
        session = SESSIONS[user_id]
        session.last_active = time.time()

        await update.message.reply_text(
            f"🧱 *Local AI Agent Bot*\n\n"
            f"Model: `{LLM_MODEL}`\n"
            f"Server: `{LLM_URL}`\n"
            f"Device: *Android* 📱\n\n"
            f"Everything runs *locally* on your phone.\n"
            f"No data leaves your device.\n\n"
            f"Select a mode or type your request directly:",
            reply_markup=self._keyboard(),
            parse_mode="Markdown",
        )

    async def help_cmd(self, update, context):
        text = (
            "🧱 *Local AI Agent Bot — Help*\n\n"
            "*Commands:*\n"
            "• /start — Show main menu\n"
            "• /status — Check system status\n"
            "• /history — Show conversation history\n"
            "• /clear — Clear history\n\n"
            "*Admin Commands:*\n"
            "• /start_llm — Start LLM server\n"
            "• /stop_llm — Stop LLM server (free RAM)\n\n"
            "*Agent Modes:*\n"
            "🧠 Code — Write code\n"
            "🔍 Review — Review code\n"
            "📖 Explain — Explain concepts\n"
            "📋 Plan — Break tasks into steps\n"
            "🐛 Debug — Fix errors\n"
            "🔄 Pipeline — Run full multi-agent workflow\n\n"
            "*Tips:*\n"
            "• Send code in triple backticks for best results\n"
            "• Use /stop_llm when not using to save RAM\n"
            "• Replies include the agent's context"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def status(self, update, context):
        try:
            import psutil
            mem = psutil.virtual_memory()
            mem_used = mem.used / (1024**3)
            mem_total = mem.total / (1024**3)
            mem_pct = mem.percent

            # Check LLM server
            try:
                r = httpx.get(LLM_URL.replace("/v1/chat/completions", ""), timeout=3)
                llm_status = "✅ Running"
            except:
                llm_status = "❌ Stopped"

            text = (
                f"📊 *System Status*\n\n"
                f"🤖 LLM Server: {llm_status}\n"
                f"🧠 Model: `{LLM_MODEL}`\n"
                f"💾 RAM: {mem_used:.1f}GB / {mem_total:.1f}GB ({mem_pct}%)\n"
                f"📱 Platform: Android (Termux)\n"
            )

            if mem_pct > 85:
                text += "\n⚠️ *RAM is high!* Consider /stop_llm"

        except Exception as e:
            text = f"⚠️ Error: {e}"

        await update.message.reply_text(text, parse_mode="Markdown")

    async def history(self, update, context):
        user_id = update.effective_user.id
        session = SESSIONS[user_id]

        if not session.history:
            await update.message.reply_text("📭 No history yet.")
            return

        lines = []
        for i, h in enumerate(session.history[-6:], 1):
            preview = h["content"][:50].replace("\n", " ")
            lines.append(f"{i}. *{h['role']}*: {preview}...")

        await update.message.reply_text(
            "📝 *Recent History*\n\n" + "\n".join(lines),
            parse_mode="Markdown",
        )

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
        # Show typing
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action="typing"
        )

        system = AGENTS.get(session.mode, AGENTS["code"])
        response = await self.llm.chat(system, text, session.history)

        # Save to history
        session.history.append({"role": "user", "content": text})
        session.history.append({"role": "assistant", "content": response})

        # Truncate history
        if len(session.history) > MAX_HISTORY * 2:
            session.history = session.history[-MAX_HISTORY * 2:]

        # Send response (split if too long)
        if len(response) > 4000:
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            await update.message.reply_text(response, parse_mode="Markdown")

    async def _run_pipeline(self, update, task, user_id):
        chat_id = update.effective_chat.id
        session = SESSIONS[user_id]

        # Step 1: Plan
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        plan = await self.llm.chat(AGENTS["plan"], f"Break this task into steps: {task}")
        await update.message.reply_text(
            f"📋 *Step 1: Planner*\n\n{plan[:3000]}",
            parse_mode="Markdown",
        )

        # Step 2: Code
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        code = await self.llm.chat(
            AGENTS["code"],
            f"Task: {task}\n\nPlan:\n{plan}\n\nWrite the complete, runnable code."
        )
        await update.message.reply_text(
            f"💻 *Step 2: Coder*\n\n```python\n{code[:3000]}\n```",
            parse_mode="Markdown",
        )

        # Step 3: Review
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        review = await self.llm.chat(AGENTS["review"], f"Review this code:\n\n{code}")
        await update.message.reply_text(
            f"🔍 *Step 3: Reviewer*\n\n{review[:3000]}",
            parse_mode="Markdown",
        )

        # Step 4: Summary
        summary = (
            f"✅ *Pipeline Complete!*\n\n"
            f"Task: {task[:100]}\n"
            f"📋 Plan: {len(plan)} chars\n"
            f"💻 Code: {len(code)} chars\n"
            f"🔍 Review: {len(review)} chars\n\n"
            f"_All generated locally on your phone 📱_"
        )
        await update.message.reply_text(summary, parse_mode="Markdown")

    # ── Admin Commands ────────────────────────────────────────────
    async def start_llm(self, update, context):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ Admin only.")
            return

        # Check if already running
        try:
            httpx.get(LLM_URL.replace("/v1/chat/completions", ""), timeout=2)
            await update.message.reply_text("🤖 LLM server is already running.")
            return
        except:
            pass

        # Start llama.cpp server
        model_path = os.path.expanduser("~/models/qwen2.5-3b.gguf")
        if not Path(model_path).exists():
            await update.message.reply_text(
                f"❌ Model not found: `{model_path}`\n"
                f"Download it first with the install script.",
                parse_mode="Markdown",
            )
            return

        cmd = (
            f"nohup {os.path.expanduser('~/llama.cpp/build/bin/llama-server')} "
            f"-m {model_path} -c 4096 --port 8080 "
            f"> /dev/null 2>&1 &"
        )
        os.system(cmd)

        await update.message.reply_text(
            "🚀 *Starting LLM server...*\n"
            "Wait 10-15 seconds, then check /status",
            parse_mode="Markdown",
        )

    async def stop_llm(self, update, context):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔ Admin only.")
            return

        os.system("pkill -f llama-server")
        await update.message.reply_text(
            "🛑 *LLM server stopped.*\n"
            "RAM freed. Use /start_llm to restart.",
            parse_mode="Markdown",
        )

    # ── Run ─────────────────────────────────────────────────────────
    def run(self):
        from telegram.ext import (
            Application, CommandHandler, MessageHandler,
            CallbackQueryHandler, ContextTypes, filters
        )

        app = Application.builder().token(self.token).build()

        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help_cmd))
        app.add_handler(CommandHandler("status", self.status))
        app.add_handler(CommandHandler("history", self.history))
        app.add_handler(CommandHandler("clear", self.clear))
        app.add_handler(CommandHandler("start_llm", self.start_llm))
        app.add_handler(CommandHandler("stop_llm", self.stop_llm))
        app.add_handler(CallbackQueryHandler(self.button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))

        logger.info("Bot starting...")
        app.run_polling(drop_pending_updates=True)

# ── Main ────────────────────────────────────────────────────────────
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
        print()
        sys.exit(1)

    llm = LLMClient(LLM_URL, LLM_MODEL)
    bot = AgentBot(TELEGRAM_BOT_TOKEN, llm)
    bot.run()

if __name__ == "__main__":
    main()
