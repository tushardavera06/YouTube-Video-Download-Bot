import os

class Config(object):
    # Bot token from BotFather
    BOT_TOKEN = os.environ.get("BOT_TOKEN") or ""

    # Telegram API ID (safe conversion - no more int(None) error)
    API_ID = int(os.environ.get("API_ID") or 0)

    # Telegram API HASH
    API_HASH = os.environ.get("API_HASH") or ""

    # Force Subscribe channel ID (optional)
    CHANNEL = os.environ.get("CHANNEL") or ""

    # Proxy (optional, keep blank)
    HTTP_PROXY = ""
