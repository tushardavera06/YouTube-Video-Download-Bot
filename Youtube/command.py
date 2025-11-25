# ============================================================
#   Commands Module (start / about / help)
#   Developer: Tushar Davera (@tushardavera)
# ============================================================

import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from Youtube.config import Config
from Youtube.script import Translation
from Youtube.forcesub import handle_force_subscribe

# Time-based greeting
current_time = datetime.datetime.now()
if current_time.hour < 12:
    WISH = "Good morning 🌞"
elif 12 <= current_time.hour < 18:
    WISH = "Good afternoon 🌤️"
else:
    WISH = "Good evening 🙂"


# =======================
#  Cancel button
# =======================
@Client.on_callback_query(filters.regex("cancel"))
async def cancel(client, callback_query):
    await callback_query.message.delete()


# =======================
#  /about command
# =======================
@Client.on_message(filters.private & filters.command("about"))
async def about(client, message):
    if Config.CHANNEL:
        fsub = await handle_force_subscribe(client, message)
        if fsub == 400:
            return

    await message.reply_text(
        Translation.ABOUT_TXT,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⛔ Close", callback_data="cancel")]]
        ),
    )


# =======================
#  /start command
# =======================
@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):
    if Config.CHANNEL:
        fsub = await handle_force_subscribe(client, message)
        if fsub == 400:
            return

    # Spidy Gaming private channel invite link
    invite_link = "https://t.me/+lbCGid5OABQ4MTE1"

    await message.reply_text(
        Translation.START_TEXT.format(message.from_user.first_name, WISH),
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📍 Update Channel", url=invite_link)],

                [
                    InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/tushardavera"),
                    InlineKeyboardButton("👥 Support", url="https://t.me/tushardavera"),
                ],

                [InlineKeyboardButton("⛔ Close", callback_data="cancel")],
            ]
        ),
        disable_web_page_preview=True,
    )


# =======================
#  /help command
# =======================
@Client.on_message(filters.private & filters.command("help"))
async def help_cmd(client, message):
    if Config.CHANNEL:
        fsub = await handle_force_subscribe(client, message)
        if fsub == 400:
            return

    await message.reply_text(
        Translation.HELP_TXT,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⛔ Close", callback_data="cancel")]]
        ),
    )
