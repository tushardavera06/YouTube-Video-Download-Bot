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
import yt_dlp
import logging
import uuid
import aiohttp
import aiofiles
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from Youtube.config import Config
from Youtube.fix_thumb import fix_thumb
from Youtube.forcesub import handle_force_subscribe, humanbytes


YT_CACHE = {}


@Client.on_message(filters.regex(r'^(http(s)?://)?(www\.)?(youtube\.com|youtu\.be)/.+'))
async def youtube_downloader(client, message):
    if Config.CHANNEL:
        fsub = await handle_force_subscribe(client, message)
        if fsub == 400:
            return

    url = message.text.strip()
    processing_msg = await message.reply_text("🔍 **Fetching available formats...**")

    ydl_opts = {"quiet": True, "cookiefile": "cookies.txt"}
    buttons = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get("formats", [])
            duration = info.get("duration")
            title = info.get("title", "YouTube Video")

            vid_key = str(uuid.uuid4())[:8]
            YT_CACHE[vid_key] = url

            # 👉 Yahi part change kiya gaya hai (buttons ka text)
            for f in formats:
                fmt_id = f.get("format_id")
                ext = f.get("ext")
                height = f.get("height")

                # Sirf wahi formats jisme video + audio dono ho
                acodec = f.get("acodec")
                vcodec = f.get("vcodec")
                if (not fmt_id) or (not acodec) or acodec == "none" or (not vcodec) or vcodec == "none":
                    continue

                # 720p / 480p / 360p...
                resolution = f"{height}p" if height else "Unknown"

                # Final button text -> 91 - 720p - mp4
                text = f"{fmt_id} - {resolution} - {ext}"

                cb = f"ytdl|{vid_key}|{fmt_id}|{ext}|video"

                if len(cb.encode()) <= 64:
                    buttons.append([InlineKeyboardButton(text, callback_data=cb)])

            # Audio only option
            if duration:
                buttons.append([
                    InlineKeyboardButton("🎵 Audio MP3", callback_data=f"ytdl|{vid_key}|bestaudio|mp3|audio")
                ])

            await message.reply_text(
                f"**✅ Available formats for:**\n`{title}`",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

            await processing_msg.delete()

    except Exception as e:
        logging.exception("Error fetching formats:")
        await processing_msg.edit_text(f"❌ Error: `{e}`")


@Client.on_callback_query(filters.regex(r"^ytdl\|"))
async def handle_download(client, cq):
    try:
        _, vid_key, fmt_id, ext, mode = cq.data.split("|")
        url = YT_CACHE.get(vid_key)
        if not url:
            await cq.message.edit_text("⚠️ Session expired. Please resend link.")
            return

        await cq.message.edit_text("⬇️ **Downloading...**")

        os.makedirs("downloads", exist_ok=True)
        output = f"downloads/{vid_key}.%(ext)s"

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
            # Sirf selected format download hoga (video+audio)
            ydl_opts = {
                "format": fmt_id,
                "outtmpl": output,
                "quiet": True,
                "cookiefile": "cookies.txt",
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "YouTube Video")
            duration = info.get("duration", 0)
            width = info.get("width")
            height = info.get("height")
            thumb_url = info.get("thumbnail")
            filesize = info.get("filesize") or info.get("filesize_approx")
            file_size_text = humanbytes(filesize) if filesize else "Unknown"

        # Audio ke liye mp3, warna selected ext
        file_path = f"downloads/{vid_key}.{'mp3' if mode == 'audio' else ext}"

        thumb_path = None
        if thumb_url:
            async with aiohttp.ClientSession() as s:
                async with s.get(thumb_url) as r:
                    if r.status == 200:
                        thumb_path = f"{vid_key}.jpg"
                        async with aiofiles.open(thumb_path, "wb") as f:
                            await f.write(await r.read())

        width, height, thumb_path = await fix_thumb(thumb_path)

        await cq.message.edit_text("📤 **Uploading...**")

        if mode == "audio":
            await client.send_audio(
                chat_id=cq.message.chat.id,
                audio=file_path,
                caption=f"🎵 **{title}**\n📦 Size: `{file_size_text}`",
                duration=duration,
                thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
            )
        else:
            await client.send_video(
                chat_id=cq.message.chat.id,
                video=file_path,
                caption=f"🎬 **{title}**\n📦 Size: `{file_size_text}`",
                width=width,
                height=height,
                duration=duration,
                thumb=thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                supports_streaming=True
            )

        await cq.message.edit_text("✅ **Successfully Uploaded!**")

        if os.path.exists(file_path):
            os.remove(file_path)
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

    except Exception as e:
        logging.exception("Download error:")
        await cq.message.edit_text(f"❌ Error: `{e}`")
