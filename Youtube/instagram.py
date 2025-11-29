# ============================================================
#   Module: Instagram Video / Reels / Photo Downloader
#   Developer: Tushar Davera (Modifications)
#   Description:
#       - Download public Instagram reels, videos, and photos
#       - Uses yt-dlp (same as YouTube module)
#       - Integrated with Admin Control System (users, block, rate-limit, stats)
# ============================================================

import os
import uuid
import logging

import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import Message

from Youtube.config import Config
from Youtube.forcesub import handle_force_subscribe, humanbytes

# Admin system hooks
try:
    from .admin_system import (
        register_user,
        is_blocked,
        is_rate_limited,
        add_download_stat,
    )
except Exception:
    # fallback – if admin_system not found for some reason
    def register_user(user): ...
    def is_blocked(user_id: int) -> bool: return False
    def is_rate_limited(user_id: int) -> bool: return False
    def add_download_stat(user_id: int, file_size_bytes: int): ...


LOG = logging.getLogger(__name__)

# Telegram size safety limit (~1.9 GB)
TELEGRAM_MAX_BYTES = 1_900_000_000

# Download directory (same as YouTube)
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# =========================
#  INSTAGRAM URL HANDLER
# =========================

INSTAGRAM_REGEX = r"(https?://)?(www\.)?(instagram\.com|instagr\.am)/[^\s]+"


@Client.on_message(filters.regex(INSTAGRAM_REGEX))
async def instagram_downloader(client: Client, message: Message):
    """
    Handle Instagram public URLs:
    - Reels
    - Posts (photos/videos)
    - IGTV (if public & supported by yt-dlp)
    """

    user = message.from_user

    # ---- Admin system: register + block + rate-limit ----
    if user:
        try:
            register_user(user)
        except Exception:
            pass

        if is_blocked(user.id):
            await message.reply_text("🚫 You are blocked from using this bot.")
            return

        if is_rate_limited(user.id):
            await message.reply_text("⏳ Too many requests, thoda baad me try karo.")
            return

    # ---- Force subscribe (same as YouTube) ----
    if Config.CHANNEL:
        fsub = await handle_force_subscribe(client, message)
        if fsub == 400:
            return

    # Extract Instagram URL from message text
    raw_text = message.text.strip()
    url = None
    for part in raw_text.split():
        if "instagram.com" in part or "instagr.am" in part:
            url = part
            break

    if not url:
        await message.reply_text("❌ Instagram link detect nahi hua. Please send a valid URL.")
        return

    processing_msg = await message.reply_text("📥 **Fetching Instagram media...**")

    # Temporary unique prefix for this download
    uid = uuid.uuid4().hex[:8]
    outtmpl = os.path.join(DOWNLOAD_DIR, f"insta_{uid}.%(ext)s")

    # yt-dlp options for Instagram
    ydl_opts = {
        "quiet": True,
        "outtmpl": outtmpl,
        "nocheckcertificate": True,
        "noplaylist": False,          # if it's a post with multiple media, yt-dlp may treat as playlist
        "cookiefile": "cookies.txt",  # optional; if cookies.txt has IG cookies, private-ish public posts also work
    }

    file_path = None
    title = "Instagram Media"
    filesize = None
    ext = None

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First extract & download
            info = ydl.extract_info(url, download=True)

            # Handle album/playlist: take first entry for sending
            if info.get("_type") == "playlist" and info.get("entries"):
                first = info["entries"][0]
                title = first.get("title") or info.get("title") or "Instagram Media"
                ext = first.get("ext") or "mp4"
                # Determine local file path
                file_path = ydl.prepare_filename(first)
                filesize = first.get("filesize") or first.get("filesize_approx")
            else:
                title = info.get("title", "Instagram Media")
                ext = info.get("ext") or "mp4"
                file_path = ydl.prepare_filename(info)
                filesize = info.get("filesize") or info.get("filesize_approx")

        # If filesize missing, use local file size
        if file_path and os.path.exists(file_path) and not filesize:
            filesize = os.path.getsize(file_path)

        # Size safety check
        if filesize and filesize > TELEGRAM_MAX_BYTES:
            await processing_msg.edit_text(
                "❌ File size 2GB se zyada hai, Telegram limit ke bahar hai.\n"
                "Chhota ya short reel try karo."
            )
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            return

        file_size_text = humanbytes(filesize) if filesize else "Unknown"

        # Decide how to send (video/photo/document)
        await processing_msg.edit_text("📤 **Uploading Instagram media...**")

        caption = f"📸 **Instagram Media**\n📝 `{title}`\n📦 Size: `{file_size_text}`"

        if not file_path or not os.path.exists(file_path):
            await processing_msg.edit_text("❌ Download failed: file not found.")
            return

        send_ext = (ext or "").lower()

        # Common video extensions
        video_exts = {"mp4", "webm", "mkv", "mov"}
        image_exts = {"jpg", "jpeg", "png", "webp"}

        if send_ext in video_exts:
            await client.send_video(
                chat_id=message.chat.id,
                video=file_path,
                caption=caption,
                supports_streaming=True,
            )
        elif send_ext in image_exts:
            await client.send_photo(
                chat_id=message.chat.id,
                photo=file_path,
                caption=caption,
            )
        else:
            # Fallback as document
            await client.send_document(
                chat_id=message.chat.id,
                document=file_path,
                caption=caption,
            )

        await processing_msg.edit_text("✅ **Instagram media sent successfully!**")

        # Admin stats update
        try:
            if user and file_path and os.path.exists(file_path):
                size_bytes = os.path.getsize(file_path)
                add_download_stat(user.id, size_bytes)
        except Exception:
            pass

    except yt_dlp.utils.DownloadError as e:
        LOG.exception("Instagram download error:")
        try:
            await processing_msg.edit_text(
                "❌ Instagram se download nahi ho paya.\n"
                "• Ho sakta hai post private ho.\n"
                "• Ya link invalid ho.\n\n"
                f"`{e}`"
            )
        except Exception:
            pass

    except Exception as e:
        LOG.exception("Instagram handler error:")
        try:
            await processing_msg.edit_text(f"❌ Unexpected error:\n`{e}`")
        except Exception:
            pass

    finally:
        # Cleanup local file
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
