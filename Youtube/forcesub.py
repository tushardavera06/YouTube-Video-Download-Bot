# ============================================================
#   Module: Force Subscribe (Advanced)
#   Developer: Tushar Davera (@tushardavera)
#   Features:
#       • Single / Multi-channel force-subscribe
#       • Auto invite-link for private channels
#       • "JOIN KAR LIYA" button with re-check
#       • humanbytes() helper used by other modules
# ============================================================

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    CallbackQuery,
)
from pyrogram.errors import UserNotParticipant

from Youtube.config import Config


# =========================
#  Size helper (for youtube.py)
# =========================

def humanbytes(size: int) -> str:
    """
    Converts bytes to human-readable format.
    Example: 1048576 -> 1.0 MB
    """
    if not size:
        return "0 B"

    power = 2 ** 10
    raised_to_pow = 0
    units = {0: "B", 1: "KB", 2: "MB", 3: "GB", 4: "TB"}

    while size > power and raised_to_pow < 4:
        size /= power
        raised_to_pow += 1

    return f"{round(size, 2)} {units[raised_to_pow]}"


# =========================
#  Internal helpers
# =========================

def _get_channels():
    """
    CHANNEL env se list banata hai.
    Support:
        "-100id"           -> one channel
        "@chan1 @chan2"    -> multiple
        "-100id,@chan2"    -> comma / space dono
    """
    raw = str(Config.CHANNEL or "").replace(",", " ").split()
    return [c.strip() for c in raw if c.strip()]


def _display_name(ch: str) -> str:
    """Channel ka clean display name."""
    ch = str(ch)
    if ch.startswith("@"):
        return ch
    if ch.startswith("-100"):
        return f"ID: {ch}"
    return ch


async def _make_join_url(client: Client, ch: str) -> str:
    """
    Private channel ID ke liye export_chat_invite_link use karega.
    Username (@channel) ke liye direct t.me link.
    """
    ch = str(ch)

    # Public channel: @username
    if ch.startswith("@"):
        return f"https://t.me/{ch[1:]}"

    # Private ID ( -100xxxx )
    if ch.startswith("-100"):
        try:
            return await client.export_chat_invite_link(ch)
        except Exception as e:
            print(f"[ForceSub] invite_link error for {ch}: {e}")
            return "https://t.me/"

    # Fallback
    return f"https://t.me/{ch}"


# =========================
#  Main Force-Sub checker
# =========================

async def handle_force_subscribe(client: Client, message: Message) -> int:
    """
    Check karta hai user ne CHANNEL(S) join kiye hain ya nahi.

    Returns:
        200 -> user allowed
        400 -> user blocked (must join first)
    """

    channels = _get_channels()
    if not channels:
        # Force-sub disabled
        return 200

    user_id = message.from_user.id
    missing = []  # jin channels me user nahi hai

    for ch in channels:
        try:
            member = await client.get_chat_member(ch, user_id)

            if member.status in ("left", "kicked", "banned"):
                missing.append(ch)

        except UserNotParticipant:
            missing.append(ch)
        except Exception as e:
            # Kisi ek channel me error aaye to usko skip karenge
            print(f"[ForceSub] get_chat_member error for {ch}: {e}")

    if not missing:
        # All channels joined
        return 200

    # User ko join karwane ka message banaate hain
    buttons = []
    for ch in missing:
        url = await _make_join_url(client, ch)
        buttons.append(
            [InlineKeyboardButton(f"📢 JOIN { _display_name(ch) }", url=url)]
        )

    # Re-check button
    buttons.append(
        [InlineKeyboardButton("✅ JOIN KAR LIYA", callback_data="check_fsub")]
    )

    # Message text
    text_lines = ["⚠️ **Pehle hamare channel(s) join karo:**", ""]
    for ch in channels:
        text_lines.append(f"• `{_display_name(ch)}`")
    text_lines.append("")
    text_lines.append("Phir niche **JOIN KAR LIYA** dabao ya dobara YouTube link bhejo.")

    await message.reply_text(
        "\n".join(text_lines),
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True,
    )

    return 400


# =========================
#  Callback: JOIN KAR LIYA
# =========================

@Client.on_callback_query(filters.regex("^check_fsub$"))
async def check_force_subscribe(client: Client, cq: CallbackQuery):
    """
    User ne 'JOIN KAR LIYA' dabaya – dobara verify karke status batata hai.
    """

    channels = _get_channels()
    if not channels:
        await cq.answer("Force-sub band hai.", show_alert=True)
        return

    user_id = cq.from_user.id
    missing = []

    for ch in channels:
        try:
            member = await client.get_chat_member(ch, user_id)
            if member.status in ("left", "kicked", "banned"):
                missing.append(ch)
        except UserNotParticipant:
            missing.append(ch)
        except Exception as e:
            print(f"[ForceSub] recheck error for {ch}: {e}")

    if not missing:
        # Sab join ho gaye
        channels_text = ", ".join(_display_name(c) for c in channels)
        try:
            await cq.message.edit_text(
                f"✅ Shukriya! Aap **{channels_text}** join kar chuke ho.\n"
                "Ab aap normal tarike se bot use kar sakte ho.\n\n"
                "Koi bhi YouTube link bhejo 👇"
            )
        except Exception:
            pass

        await cq.answer("Now you are verified ✅", show_alert=False)
        return

    # Abhi bhi kuch channels baaki hain
    missing_text = ", ".join(_display_name(c) for c in missing)
    await cq.answer(
        f"❌ Abhi bhi in channel(s) ko join nahi kiya:\n{missing_text}",
        show_alert=True,
    )
