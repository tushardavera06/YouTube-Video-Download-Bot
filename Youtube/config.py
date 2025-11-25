# ============================================================
#   Config Module
#   All secret values env se aayenge (Railway / Heroku vars)
#   Force-subscribe ke liye CHANNEL env jaruri hai.
# ============================================================

import os


class Config(object):

    # Bot token from @BotFather
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

    # API ID & HASH from https://my.telegram.org
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")

    # Force Subscribe:
    # Railway me CHANNEL env me yahi value rakho:
    #   -1001927269871       (Spidy Gaming ka channel ID)
    #
    # Agar future me multiple channels chahie ho:
    #   "-100id1 @second_channel"
    CHANNEL = os.environ.get("CHANNEL", "")

    # Agar koi HTTP proxy use karna ho to yaha env se doge
    # warna empty rehne do
    HTTP_PROXY = os.environ.get("HTTP_PROXY", "")
