# ©️ LISA-KOREA | @LISA_FAN_LK | NT_BOT_CHANNEL | LISA-KOREA/YouTube-Video-Download-Bot

# [⚠️ Do not change this repo link ⚠️] :- https://github.com/LISA-KOREA/YouTube-Video-Download-Bot

import os
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional

import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)

from Youtube.config import Config
from Youtube.fix_thumb import fix_thumb
from Youtube.forcesub import handle_force_subscribe, humanbytes

# =====================
# GLOBALS / SETTINGS
# =====================

YT_CACHE: Dict[str, Dict[str, Any]] = {}

TELEGRAM_MAX_BYTES = 1_900_000_000
MAX_DURATION_SECONDS = 60 * 60

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

LOG = logging.getLogger(__name__)


# =====================
# HELPERS
# =====================

def get_yt_info(url: str) -> Dict[str, Any]:
    ydl_opts = {"quiet": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def build_keyboard(cache_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("🎵 Audio (Best)", callback_data=f"yt_dl|{cache_id}|audio")],
        [
            InlineKeyboardButton("🎥 360p", callback_data=f"yt_dl|{cache_id}|360p"),
            InlineKeyboardButton("🎥 720p", callback_data=f"yt_dl|{cache_id}|720p"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"yt_dl|{cache_id}|cancel")],
    ]
    return InlineKeyboardMarkup(buttons)


def get_format_selector(choice: str) -> str:
    if choice == "audio":
        return "bestaudio/best"
    elif choice == "360p":
        return "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]"
    elif choice == "720p":
        return "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]"
    return "best"


def pick_estimated_size(info: Dict[str, Any]) -> Optional[int]:
    size = info.get("filesize") or info.get("filesize_approx")
    if size:
        return int(size)
    for f in info.get("formats", []):
        if f.get("filesize"):
            return int(f["filesize"])
        if f.get("filesize_approx"):
            return int(f["filesize_approx"])
    return None


# =====================
# MESSAGE HANDLER
# =====================

@Client.on_message(filters.regex(r"(youtube\.com|youtu\.be)") & ~filters.edited)
async def youtube_downloader(client: Client, message: Message):
    if Config.CHANNEL:
        fsub = await handle_force_subscribe(client, message)
        if fsub == 400:
            return

    url = message.text.strip()
    msg = await message.reply_text("🔍 Video info fetch ho rahi hai...")

    try:
        info = get_yt_info(url)
    except:
        await msg.edit("❌ Video info nahi mil paayi. Thodi der baad try karo.")
        return

    duration = info.get("duration", 0)
    if duration > MAX_DURATION_SECONDS:
        await msg.edit("❌ Ye video 1 ghante se lambi hai. Chhoti video bhejo.")
        return

    title = info.get("title") or "YouTube Video"
    thumb = info.get("thumbnail")
    duration_str = info.get("duration_string", "")

    cache_id = str(uuid.uuid4())
    YT_CACHE[cache_id] = {"url": url, "info": info, "user": message.from_user.id}

    caption = f"📺 **{title}**\n⏱ Duration: `{duration_str}`\n\n👇 Format select karo:"

    if thumb:
        thumb_path = await fix_thumb(thumb, title)
        await msg.delete()
        await message.reply_photo(thumb_path, caption=caption, reply_markup=build_keyboard(cache_id))
        os.remove(thumb_path)
    else:
        await msg.edit(caption, reply_markup=build_keyboard(cache_id))


# =====================
# CALLBACK HANDLER
# =====================

@Client.on_callback_query(filters.regex(r"^yt_dl\|"))
async def yt_cb(client: Client, query: CallbackQuery):
    _, cache_id, choice = query.data.split("|")

    data = YT_CACHE.get(cache_id)
    if not data:
        await query.answer("⏰ Request expire ho gayi.", show_alert=True)
        return

    if query.from_user.id != data["user"]:
        await query.answer("Sirf jisne link bheja tha, wo hi use kar sakta hai.", show_alert=True)
        return

    if choice == "cancel":
        await query.message.edit_caption("❌ Cancelled.")
        YT_CACHE.pop(cache_id, None)
        return

    url = data["url"]
    info = data["info"]

    fmt = get_format_selector(choice)
    await query.answer()

    await query.message.edit_caption(f"📥 `{choice}` selected.\n🔄 Downloading...")

    est = pick_estimated_size(info)
    if est and est > TELEGRAM_MAX_BYTES:
        await query.message.edit_caption("❌ File size 2GB se zyada hai.")
        return

    temp = str(uuid.uuid4())
    out = f"downloads/{temp}.%(ext)s"

    ydl_opts = {
        "format": fmt,
        "outtmpl": out,
        "quiet": True,
        "merge_output_format": "mp4" if choice != "audio" else "mp3",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }] if choice == "audio" else [],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            dlinfo = ydl.extract_info(url, download=True)
            file = ydl.prepare_filename(dlinfo)

        if choice == "audio":
            base, _ = os.path.splitext(file)
            if os.path.exists(base + ".mp3"):
                file = base + ".mp3"

        size = os.path.getsize(file)
        if size > TELEGRAM_MAX_BYTES:
            await query.message.edit_caption("❌ Final file 2GB se badi hai.")
            return

        title = dlinfo.get("title", "YouTube Video")
        cap = f"✅ **{title}**\nCompleted."

        if choice == "audio":
            await query.message.reply_audio(file, caption=cap)
        else:
            await query.message.reply_video(file, caption=cap, supports_streaming=True)

        await query.message.edit_caption(f"✅ Done! Size: `{humanbytes(size)}`")

    except Exception as e:
        await query.message.edit_caption("❌ Error aaya. Dusra link try karo.")
        print(e)

    try:
        os.remove(file)
    except:
        pass

    YT_CACHE.pop(cache_id, None)
