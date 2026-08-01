import os
import sys
import glob
import subprocess
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
SCRIPTS_DIR = os.path.join(MBM_ROOT, "Scripts")
ARTIFACTS_DIR = os.path.join(MBM_ROOT, "Artifacts")
CONFIG_DIR = os.path.join(MBM_ROOT, "Config")

# Hardcoded for the user's specific Telegram bot
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
# Security: only respond to the user's specific chat ID
AUTHORIZED_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID", "0"))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"[DEBUG] Received /start from Chat ID: {update.effective_chat.id}")
    if update.effective_chat.id != AUTHORIZED_CHAT_ID:
        print(f"[WARN] Unauthorized access attempt from {update.effective_chat.id}")
        return
    await update.message.reply_text("MBM Interactive Bot is online. Type /help to see available commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"[DEBUG] Received /help from Chat ID: {update.effective_chat.id}")
    if update.effective_chat.id != AUTHORIZED_CHAT_ID:
        return
    text = (
        "🤖 *MBM Command Menu*\n\n"
        "/status - Check the Lead Engine heartbeat\n"
        "/run_engine - Manually start a full pipeline run (in background)\n"
        "/latest_leads - Download the most recent lead packs\n"
        "/ping - Check if I am awake"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"[DEBUG] Received /ping from Chat ID: {update.effective_chat.id}")
    if update.effective_chat.id != AUTHORIZED_CHAT_ID:
        return
    await update.message.reply_text("Pong! I am awake and listening.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"[DEBUG] Received /status from Chat ID: {update.effective_chat.id}")
    if update.effective_chat.id != AUTHORIZED_CHAT_ID:
        return
    heartbeat_file = os.path.join(CONFIG_DIR, "heartbeat.json")
    if os.path.exists(heartbeat_file):
        with open(heartbeat_file, 'r') as f:
            content = f.read()
        await update.message.reply_text(f"💓 *Heartbeat Status:*\n```json\n{content}\n```", parse_mode='Markdown')
    else:
        await update.message.reply_text("Heartbeat file not found. Engine may not have run yet.")

async def run_engine(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != AUTHORIZED_CHAT_ID:
        return
    await update.message.reply_text("🚀 Starting MBM Lead Engine in the background. It will send a summary when complete.")
    
    script_path = os.path.join(SCRIPTS_DIR, "lead_engine_forever.ps1")
    # Launch in a detached process so it doesn't block the bot
    subprocess.Popen(
        ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path],
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )

async def latest_leads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.id != AUTHORIZED_CHAT_ID:
        return
    
    await update.message.reply_text("Fetching latest leads...")
    
    # Find latest packs
    buyer_files = sorted(glob.glob(os.path.join(ARTIFACTS_DIR, "buyer_contacts_*.csv")), reverse=True)
    seller_files = sorted(glob.glob(os.path.join(ARTIFACTS_DIR, "distressed_sellers_*.csv")), reverse=True)
    
    sent_any = False
    if buyer_files:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=open(buyer_files[0], 'rb'), caption="Latest Buyer Contacts")
        sent_any = True
    if seller_files:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=open(seller_files[0], 'rb'), caption="Latest Distressed Sellers")
        sent_any = True
        
    if not sent_any:
        await update.message.reply_text("Could not find any recent lead files in Artifacts.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"[DEBUG] Received text message from Chat ID: {update.effective_chat.id} -> {update.message.text}")
    if update.effective_chat.id != AUTHORIZED_CHAT_ID:
        return
        
    user_order = update.message.text.strip()
    await update.message.reply_text(f"🧠 *Processing Order with Gemini AI...*\n`{user_order}`", parse_mode='Markdown')
    
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    
    # Process order via Gemini
    system_prompt = (
        "You are the Antigravity Master Command Bridge. You control an automated AI infrastructure.\n"
        "Available Actions:\n"
        "- 'run_publisher': Runs master publisher (video generation, lead outreach, email cadences).\n"
        "- 'purge_videos': Deletes old videos and renders fresh 1080p Shorts.\n"
        "- 'check_emails': Runs AI Ops Agent to check email replies and log errors.\n"
        "- 'wolf_closer': Triggers the Wolf of Wall Street Closer Agent.\n"
        "- 'answer': Just answer the question or query directly.\n\n"
        "Return a strict JSON object:\n"
        '{"action": "run_publisher"|"purge_videos"|"check_emails"|"wolf_closer"|"answer", "response_text": "Detailed explanation/answer to send back to user"}'
    )
    
    action = "answer"
    answer_text = "Order received and processed."
    
    if gemini_key:
        import requests, json
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_order}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }
        try:
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                data = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(data)
                action = parsed.get("action", "answer")
                answer_text = parsed.get("response_text", "")
        except Exception as e:
            print(f"[WARN] Gemini processing error: {e}")

    # Execute action if matched
    if action == "run_publisher":
        subprocess.Popen([sys.executable, os.path.join(SCRIPTS_DIR, "master_publisher.py")])
        answer_text += "\n\n🚀 *Master Publisher Launched in Background!*"
    elif action == "purge_videos":
        purger_script = os.path.join(MBM_ROOT, "..", "clipping-factory", "MBM-Social", "niche_channel_purger_and_renderer.py")
        subprocess.Popen([sys.executable, purger_script])
        answer_text += "\n\n🎬 *Video Purger & Renderer Launched!*"
    elif action == "check_emails":
        ops_script = os.path.join(SCRIPTS_DIR, "ai_ops_agent.py")
        subprocess.Popen([sys.executable, ops_script])
        answer_text += "\n\n📬 *AI Ops Email & Log Inspector Launched!*"
    elif action == "wolf_closer":
        closer_script = os.path.join(MBM_ROOT, "LeadEngine", "wolf_closer_agent.py")
        subprocess.Popen([sys.executable, closer_script, "--once"])
        answer_text += "\n\n🐺 *Wolf Closer Agent Triggered!*"
        
    await update.message.reply_text(answer_text, parse_mode='Markdown')

def main():
    print("Starting MBM Telegram Listener...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("run_engine", run_engine))
    app.add_handler(CommandHandler("latest_leads", latest_leads))
    
    # Handle normal text for vibe coding
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot is polling for commands...")
    app.run_polling()

if __name__ == "__main__":
    main()
