# ============================================================
#   Module: Start / About / Help Handlers
#   Developer: Tushar Davera (@tushardavera)
#   Description:
#       /start, /about, /help commands + cancel button
# ============================================================

import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from Youtube.config import Config
from Youtube.script import Translation
from Youtube.forcesub import handle_force_subscribe

# =========================
# Time-based greeting
# =========================

current_time = datetime.datetime.now()
if current_time.hour < 12:
    wish = "Good morning 🌞"
elif 12 <= current_time.hour < 18:
    wish = "Good afternoon 🌤️"
else:
    wish = "Good evening 🌝"


# =========================
# Cancel button handler
# =========================

@Client.on_callback_query(filters.regex("cancel"))
async def cancel(client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception:
        pass


# =========================
# /about command
# =========================

@Client.on_message(filters.private & filters.command("about"))
async def about(client, message):
    if Config.CHANNEL:
        fsub = await handle_force_subscribe(client, message)
        if fsub == 400:
            return

    await message.reply_text(
        text=Translation.ABOUT_TXT,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton('⛔️ Close', callback_data='cancel')]
            ]
        )
    )


# =========================
# /start command
# =========================

@Client.on_message(filters.private & filters.command("start"))
async def start(client, message):
    if Config.CHANNEL:
        fsub = await handle_force_subscribe(client, message)
        if fsub == 400:
            return

    await message.reply_text(
        text=Translation.START_TEXT.format(message.from_user.first_name, wish),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton('📍 Update Channel', url='https://t.me/Ethicals_hacking'),
                ],
                [
                    InlineKeyboardButton('👩‍💻 Developer', url='https://t.me/tushardavera'),
                    InlineKeyboardButton('👥 Support Group', url='https://t.me/Ethical_hacking_group'),
                ],
                [
                    InlineKeyboardButton('⛔️ Close', callback_data='cancel')
                ]
            ]
        )
    )


# =========================
# /help command
# =========================

@Client.on_message(filters.private & filters.command("help"))
async def help_cmd(client, message):
    if Config.CHANNEL:
        fsub = await handle_force_subscribe(client, message)
        if fsub == 400:
            return

    help_text = """
<b>How to Use This Bot?</b>

1️⃣ Send me any YouTube link  
2️⃣ I will show download options  
3️⃣ Select Audio/Video — done! 🎉

Fast, simple and clean.

©️ Channel : @Ethicals_hacking  
👨‍💻 Developer : @tushardavera
    """

    await message.reply_text(help_text)
