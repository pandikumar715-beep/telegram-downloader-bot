
import os
import asyncio
import logging
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo
from threading import Thread

import yt_dlp
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = 8951821743
FREE_LIMIT = 3
PREMIUM_USERS = set()

IST = ZoneInfo("Asia/Kolkata")
user_downloads = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

web = Flask(__name__)

@web.route("/")
def home():
    return "Namma Downloader Bot is Running!"

def download_video(url, folder):
    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(folder, "%(id)s.%(ext)s"),
        "noplaylist": True,
        "max_filesize": 49 * 1024 * 1024,
        "quiet": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        path = ydl.prepare_filename(info)
        return path, info.get("title", "Video")

def get_count(user_id):
    today = datetime.now(IST).date()
    data = user_downloads.get(user_id)

    if not data or data["date"] != today:
        user_downloads[user_id] = {
            "date": today,
            "count": 0
        }

    return user_downloads[user_id]["count"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 Welcome to Namma Downloader!\n\n"
        "📥 Send a video link to download.\n"
        "🎬 YouTube | Instagram | Facebook | TikTok\n\n"
        "🆓 Free: 3 downloads/day\n"
        "⭐ Premium: ₹59/month\n\n"
        "Send your video URL now!"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    url = update.message.text.strip()

    if not url.startswith(("https://", "http://")):
        await update.message.reply_text("❌ Send a valid video URL.")
        return

    owner = user_id == OWNER_ID
    premium = user_id in PREMIUM_USERS

    if not owner and not premium and get_count(user_id) >= FREE_LIMIT:
        await update.message.reply_text(
            "⚠️ Daily free limit reached!\n"
            "⭐ Premium subscription: ₹59/month"
        )
        return

    msg = await update.message.reply_text("⏳ Downloading your video...")

    try:
        with tempfile.TemporaryDirectory() as folder:
            path, title = await asyncio.to_thread(
                download_video, url, folder
            )

            if not os.path.exists(path):
                raise Exception("Video file not found.")

            if os.path.getsize(path) > 49 * 1024 * 1024:
                raise Exception("Video is too large. Try a lower quality.")

            with open(path, "rb") as video:
                await update.message.reply_document(
                    document=video,
                    filename=os.path.basename(path),
                    caption=f"✅ {title}\n\n🔥 Namma Downloader"
                )

        if not owner and not premium:
            user_downloads[user_id]["count"] += 1

        remaining = (
            "Unlimited" if owner or premium
            else str(FREE_LIMIT - get_count(user_id))
        )

        await msg.edit_text(
            f"✅ Download completed!\n"
            f"Remaining free downloads: {remaining}"
        )

    except Exception as e:
        logger.exception("Download failed")
        await msg.edit_text(
            "❌ Download failed. Check the link or try again later."
        )

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return

    await update.message.reply_text(
        f"👑 OWNER PANEL\n\n"
        f"Owner ID: {OWNER_ID}\n"
        f"Premium users: {len(PREMIUM_USERS)}\n"
        f"Tracked users: {len(user_downloads)}"
    )

def run_web():
    web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing!")

    Thread(target=run_web, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link)
    )

    print("Namma Downloader Bot Started!")
    app.run_polling()

if __name__ == "__main__":
    main()
