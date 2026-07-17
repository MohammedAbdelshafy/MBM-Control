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
TELEGRAM_TOKEN = "TELEGRAM_BOT_TOKEN_REDACTED"
# Security: only respond to the user's specific chat ID
AUTHORIZED_CHAT_ID = 6617518949

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
        
    await update.message.reply_text(f"✨ *Vibe Coding Initiated!*\nI have forwarded your request to Opencode to start building.", parse_mode='Markdown')
    
    # Run opencode with the user's natural language prompt
    subprocess.Popen(
        ["opencode", "run", "--auto", update.message.text],
        cwd=MBM_ROOT,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        shell=True
    )

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
