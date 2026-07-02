#!/usr/bin/env python3
"""BRICKStack Telegram Bot — connects to your backend WebSocket."""
import asyncio, json, os, sys, websockets
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BACKEND_WS = os.getenv("BRICKSTACK_WS_URL", "ws://localhost:8000/ws")
MAX_MSG_LEN = 4000  # Telegram limit

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧱 *BRICKStack Bot*\n\n"
        "Send me any task and I'll run it through the AI pipeline.\n"
        "Example: `write a python script to sort a list`",
        parse_mode="Markdown"
    )

async def send_chunked(message, text: str, parse_mode=None):
    """Send long messages in chunks."""
    while text:
        chunk = text[:MAX_MSG_LEN]
        text = text[MAX_MSG_LEN:]
        await message.reply_text(chunk, parse_mode=parse_mode)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    task_id = f"tg-{update.message.message_id}"
    
    status_msg = await update.message.reply_text("🔄 Connecting to BRICKStack...")
    
    try:
        async with websockets.connect(BACKEND_WS) as ws:
            await ws.send(json.dumps({
                "type": "user_message",
                "content": user_text,
                "task_id": task_id,
                "user_id": f"tg-{update.effective_user.id}",
                "session_context": {}
            }))
            
            code_buffer = ""
            output_buffer = ""
            answer_buffer = ""
            current_phase = "thinking"
            
            async for raw in ws:
                msg = json.loads(raw)
                mtype = msg.get("type")
                
                if mtype == "thought":
                    agent = msg.get("agent", "AI")
                    await status_msg.edit_text(f"🤔 *{agent}* is thinking...", parse_mode="Markdown")
                    
                elif mtype == "code":
                    chunk = msg.get("chunk", "")
                    code_buffer += chunk
                    if len(code_buffer) < 100 or not code_buffer.strip():
                        await status_msg.edit_text("⌨️ Writing code...")
                        
                elif mtype == "terminal":
                    output_buffer = msg.get("content", "")
                    await status_msg.edit_text("⚡ Executing...")
                    
                elif mtype == "assistant":
                    chunk = msg.get("chunk", "")
                    answer_buffer += chunk
                    
                elif mtype == "done":
                    break
                    
                elif mtype == "error":
                    await update.message.reply_text(f"❌ Error: {msg.get('content', 'Unknown')}")
                    return
            
            # Send results
            await status_msg.edit_text("✅ Done!")
            
            if code_buffer.strip():
                await update.message.reply_text(f"📄 *Generated Code:*\n```python\n{code_buffer[:3900]}\n```", parse_mode="Markdown")
            
            if output_buffer.strip():
                await update.message.reply_text(f"🖥️ *Output:*\n```\n{output_buffer[:3900]}\n```", parse_mode="Markdown")
            
            if answer_buffer.strip():
                await send_chunked(update.message, answer_buffer)
            elif not code_buffer and not output_buffer:
                await update.message.reply_text("✅ Task completed (no output).")
                
    except Exception as e:
        await status_msg.edit_text(f"❌ Failed: {str(e)[:100]}")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: Set TELEGRAM_BOT_TOKEN env var.\nGet one from @BotFather on Telegram.")
        sys.exit(1)
    
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print(f"🤖 Bot running. Backend: {BACKEND_WS}")
    print("Send /start to your bot on Telegram.")
    app.run_polling()

if __name__ == "__main__":
    main()
