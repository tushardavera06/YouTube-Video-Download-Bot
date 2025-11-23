# ============================================================
#   Project: YouTube Video & Audio Downloader Bot
#   Developer: Tushar Davera
#   Description:
#       Advanced YouTube downloader module optimized for:
#       • Fast downloads
#       • Audio/Video conversion
#       • Error handling
#       • High-quality formats
# ============================================================

import os
import uuid
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
# GLOBAL SETTINGS
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
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def build_keyboard(cache_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Audio (Best)", callback_data=f"yt|{cache_id}|audio")
        ],
        [
            InlineKeyboardButton("🎥 360p", callback_data=f"yt|{cache_id}|360p"),
            InlineKeyboardButton("🎥 720p", callback_data=f"yt|{cache_id}|720p"),
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data=f"yt|{cache_id}|cancel")
        ]
    ])


def get_format(choice: str) -> str:
    if choice == "audio":
        return "bestaudio/best"
    if choice == "360p":
        return "bestvideo[height<=360][ext=mp4]+bestaudio/best"
    if choice == "720p":
        return "bestvideo[height<=720][ext=mp4]+bestaudio/best"
    return "best"


def estimate_size(info: Dict[str, Any]) -> Optional[int]:
    if info.get("filesize"):
        return int(info["filesize"])
    if info.get("filesize_approx"):
        return int(info["filesize_approx"])

    for f in info.get("formats", []):
        if f.get("filesize"):
            return int(f["filesize"])
        if f.get("filesize_approx"):
            return int(f["filesize_approx"])

    return None


# =====================
# MAIN HANDLER
# =====================

@Client.on_message(filters.regex(r"(youtube\.com|youtu\.be)") & ~filters.edited)
async def youtube_start(client: Client, message: Message):

    if Config.CHANNEL:
        if await handle_force_subscribe(client, message) == 400:
            return

    url = message.text.strip()
    msg = await message.reply("🔍 Fetching video details...")

    try:
        info = get_yt_info(url)
    except:
        return await msg.edit("❌ Video details fetch nahi ho paayi.")

    # Duration check
    duration = info.get("duration", 0)
    if duration > MAX_DURATION_SECONDS:
        return await msg.edit("❌ Ye video 1 hour se badi hai. Chhoti video bhejo.")

    title = info.get("title") or "YouTube Video"
    thumb = info.get("thumbnail")
    duration_str = info.get("duration_string", "")

    cache_id = str(uuid.uuid4())

    YT_CACHE[cache_id] = {
        "url": url,
        "info": info,
        "uid": message.from_user.id
    }

    caption = f"📺 **{title}**\n⏱ Duration: `{duration_str}`\n\n👇 Format select karo:"

    if thumb:
        th = await fix_thumb(thumb, title)
        await msg.delete()
        await message.reply_photo(th, caption=caption, reply_markup=build_keyboard(cache_id))
        os.remove(th)
    else:
        await msg.edit(caption, reply_markup=build_keyboard(cache_id))


# =====================
# CALLBACK HANDLER
# =====================

@Client.on_callback_query(filters.regex(r"^yt\|"))
async def youtube_download(client: Client, query: CallbackQuery):

    _, cache_id, choice = query.data.split("|")

    data = YT_CACHE.get(cache_id)
    if not data:
        return await query.answer("⏰ Request expire ho gayi.", show_alert=True)

    if query.from_user.id != data["uid"]:
        return await query.answer("Ye buttons sirf original user ke liye hain.", show_alert=True)

    if choice == "cancel":
        await query.message.edit_caption("❌ Cancelled.")
        YT_CACHE.pop(cache_id, None)
        return

    url = data["url"]
    info = data["info"]

    fmt = get_format(choice)
    await query.answer()
    await query.message.edit_caption(f"📥 `{choice}` selected.\n⏳ Downloading...")

    est = estimate_size(info)
    if est and est > TELEGRAM_MAX_BYTES:
        return await query.message.edit_caption("❌ File size 2GB se zyada hai.")

    temp = str(uuid.uuid4())
    output = f"downloads/{temp}.%(ext)s"

    ydl_opts = {
        "format": fmt,
        "outtmpl": output,
        "quiet": True,
        "merge_output_format": "mp4" if choice != "audio" else "mp3",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }] if choice == "audio" else []
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info2 = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info2)

        if choice == "audio":
            base = file_path.rsplit(".", 1)[0]
            if os.path.exists(base + ".mp3"):
                file_path = base + ".mp3"

        size = os.path.getsize(file_path)
        if size > TELEGRAM_MAX_BYTES:
            return await query.message.edit_caption("❌ Final file 2GB se badi hai.")

        title = info2.get("title", "YouTube")
        caption = f"✅ **{title}**\nSize: `{humanbytes(size)}`"

        if choice == "audio":
            await query.message.reply_audio(file_path, caption=caption)
        else:
            await query.message.reply_video(file_path, caption=caption, supports_streaming=True)

        await query.message.edit_caption("✅ Completed ✔")

    except Exception as e:
        print(e)
        await query.message.edit_caption("❌ Download me error aaya. Try again.")

    try:
        os.remove(file_path)
    except:
        pass

    YT_CACHE.pop(cache_id, None)
