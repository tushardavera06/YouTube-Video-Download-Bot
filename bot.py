# ============================================================
#   File: bot.py
#   Project: YouTube Downloader Bot
#   Developer: Tushar Davera
#   Description:
#       Main entry point for the Telegram bot.
# ============================================================

from pyrogram import Client
from Youtube.config import Config

# Pyrogram Client (main bot)
app = Client(
    "UtubedownloadBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="Youtube")
)

if __name__ == "__main__":
    print("🚀 Utubedownload Bot started (Developer: Tushar Davera)")
    app.run()
