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

import yt_dlp
import aiohttp
import aiofiles

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

from Youtube.config import Config
from Youtube.fix_thumb import fix_thumb
from Youtube.forcesub import handle_force_subscribe, humanbytes

# >>> Admin Control System imports
from .admin_system import (
    register_user,
    add_download_stat,
    is_rate_limited,
    is_blocked
)

# Simple in-memory cache
YT_CACHE = {}

# Telegram size safety limit (~1.9 GB)
TELEGRAM_MAX_BYTES = 1_900_000_000

# Download directory
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

LOG = logging.getLogger(__name__)


# =========================
#  FETCH FORMATS HANDLER
# =========================

@Client.on_message(filters.regex(r'^(http(s)?://)?(www\.)?(youtube\.com|youtu\.be)/.+'))
async def youtube_downloader(client: Client, message: Message):

    # >>> Admin System: user register + block + rate-limit
    user = message.from_user
    if user:
        # register / update user details
        register_user(user)

        # hard block check
        if is_blocked(user.id):
            await message.reply_text("🚫 You are blocked from using this bot.")
            return

        # simple rate-limit
        if is_rate_limited(user.id):
            await message.reply_text("⏳ Bahut zyada requests, thoda baad me try karo.")
            return

    # Force subscribe check
    if Config.CHANNEL:
        fsub = await handle_force_subscribe(client, message)
        if fsub == 400:
            return

    url = message.text.strip()
    processing_msg = await message.reply_text("🔍 **Fetching available formats...**")

    ydl_opts = {
        "quiet": True,
        "cookiefile": "cookies.txt",  # optional, if exists it will be used
        "nocheckcertificate": True
    }

    buttons = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get("formats", [])
            duration = info.get("duration")
            title = info.get("title", "YouTube Video")

            # Short cache key
            vid_key = str(uuid.uuid4())[:8]
            YT_CACHE[vid_key] = url

            # Build video+audio format buttons
            for f in formats:
                fmt_id = f.get("format_id")
                ext = f.get("ext")
                height = f.get("height")
                acodec = f.get("acodec")
                vcodec = f.get("vcodec")

                # Filter only muxed (video + audio) formats
                if (not fmt_id) or (not acodec) or acodec == "none" or (not vcodec) or vcodec == "none":
                    continue

                resolution = f"{height}p" if height else "Unknown"
                text = f"{fmt_id} - {resolution} - {ext}"

                cb = f"ytdl|{vid_key}|{fmt_id}|{ext}|video"

                # Callback data 64 bytes limit
                if len(cb.encode()) <= 64:
                    buttons.append([InlineKeyboardButton(text, callback_data=cb)])

            # Audio-only button
            if duration:
                buttons.append([
                    InlineKeyboardButton(
                        "🎵 Audio MP3 (Best)",
                        callback_data=f"ytdl|{vid_key}|bestaudio|mp3|audio"
                    )
                ])

            if not buttons:
                await processing_msg.edit_text("❌ Koi valid format nahi mila. Dusra link try karo.")
                return

            await message.reply_text(
                f"**✅ Available formats for:**\n`{title}`",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            await processing_msg.delete()

    except Exception as e:
        LOG.exception("Error fetching formats:")
        await processing_msg.edit_text(f"❌ Error while fetching formats:\n`{e}`")


# =========================
#  DOWNLOAD HANDLER
# =========================

@Client.on_callback_query(filters.regex(r"^ytdl\|"))
async def handle_download(client: Client, cq: CallbackQuery):

    # >>> Admin System: block + rate-limit on callback too
    user = cq.from_user
    if user:
        if is_blocked(user.id):
            await cq.answer("You are blocked from using this bot.", show_alert=True)
            return
        if is_rate_limited(user.id):
            await cq.answer("Slow down, bahut zyada requests.", show_alert=True)
            return

    try:
        _, vid_key, fmt_id, ext, mode = cq.data.split("|")
    except ValueError:
        return await cq.message.edit_text("❌ Invalid callback data. Please resend the link.")

    url = YT_CACHE.get(vid_key)
    if not url:
        await cq.message.edit_text("⚠️ Session expired. Please resend link.")
        return

    await cq.message.edit_text("⬇️ **Downloading...**")

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    output = os.path.join(DOWNLOAD_DIR, f"{vid_key}.%(ext)s")

    if mode == "audio":
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output,
            "quiet": True,
            "cookiefile": "cookies.txt",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
    else:
        # Selected muxed video+audio format
        ydl_opts = {
            "format": fmt_id,
            "outtmpl": output,
            "quiet": True,
            "cookiefile": "cookies.txt",
        }

    file_path = None
    thumb_path = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "YouTube Video")
            duration = info.get("duration", 0)
            thumb_url = info.get("thumbnail")
            filesize = info.get("filesize") or info.get("filesize_approx")

        # Final file path resolution
        if mode == "audio":
            file_path = os.path.join(DOWNLOAD_DIR, f"{vid_key}.mp3")
        else:
            file_path = os.path.join(DOWNLOAD_DIR, f"{vid_key}.{ext}")

        # If filesize missing, try local file size
        if (not filesize) and os.path.exists(file_path):
            filesize = os.path.getsize(file_path)

        # Size safety check
        if filesize and filesize > TELEGRAM_MAX_BYTES:
            await cq.message.edit_text(
                "❌ File size 2GB se zyada hai, Telegram limit ke bahar hai.\n"
                "Chhota format ya chhoti video try karo."
            )
            if os.path.exists(file_path):
                os.remove(file_path)
            return

        file_size_text = humanbytes(filesize) if filesize else "Unknown"

        # Thumbnail download
        if thumb_url:
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(thumb_url) as r:
                        if r.status == 200:
                            thumb_path = f"{vid_key}.jpg"
                            async with aiofiles.open(thumb_path, "wb") as f:
                                await f.write(await r.read())
            except Exception as e:
                LOG.warning("Thumbnail download failed: %s", e)
                thumb_path = None

        # Fix thumb (width, height, final thumb path) – only if thumb exists
        width = height = 0
        if thumb_path and os.path.exists(thumb_path):
            try:
                width, height, thumb_path = await fix_thumb(thumb_path)
            except Exception as e:
                LOG.warning("fix_thumb failed: %s", e)
                thumb_path = None

        await cq.message.edit_text("📤 **Uploading...**")

        caption = f"**{title}**\n📦 Size: `{file_size_text}`"

        if mode == "audio":
            await client.send_audio(
                chat_id=cq.message.chat.id,
                audio=file_path,
                caption="🎵 " + caption,
                duration=duration,
                thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
            )
        else:
            await client.send_video(
                chat_id=cq.message.chat.id,
                video=file_path,
                caption="🎬 " + caption,
                width=width or None,
                height=height or None,
                duration=duration,
                thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                supports_streaming=True
            )

        await cq.message.edit_text("✅ **Successfully Uploaded!**")

        # >>> Admin System: download stats update
        try:
            if file_path and os.path.exists(file_path) and user:
                size_bytes = os.path.getsize(file_path)
                add_download_stat(user.id, size_bytes)
        except Exception:
            pass

    except Exception as e:
        LOG.exception("Download error:")
        try:
            await cq.message.edit_text(f"❌ Download error:\n`{e}`")
        except Exception:
            pass

    finally:
        # Cleanup
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass

        # Remove from cache
        YT_CACHE.pop(vid_key, None)
