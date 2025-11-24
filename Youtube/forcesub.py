# ============================================================
#   Module: Force Subscribe
#   Developer: Tushar Davera (@tushardavera)
#   Description:
#       Checks if user has joined the required channel.
#       If not, asks user to join and stops further actions.
# ============================================================

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import UserNotParticipant

from Youtube.config import Config


def humanbytes(size):
    """
    Converts bytes to human-readable format.
    Used for showing file sizes like 10 MB, 1.5 GB, etc.
    """
    if not size:
        return "0 B"

    power = 2 ** 10
    raised_to_pow = 0
    dict_power_n = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}

    while size > power:
        size /= power
        raised_to_pow += 1
    return f"{round(size, 2)} {dict_power_n[raised_to_pow]}"


async def handle_force_subscribe(client: Client, message: Message):
    """
    Checks if the user has joined the channel defined in Config.CHANNEL.
    Returns:
        200 -> user allowed
        400 -> user must join, action stopped
    """

    # Agar CHANNEL set hi nahi hai to fsub off samjho
    if not Config.CHANNEL:
        return 200

    user_id = message.from_user.id
    chat_id = Config.CHANNEL

    # CHANNEL env me tum ya to:
    #  -100XXXXXXXXXX (ID)   ya
    #  @Ethicals_hacking (username) rakh sakte ho

    try:
        member = await client.get_chat_member(chat_id, user_id)

        # Agar band / restricted ho
        if member.status in ("kicked", "banned"):
            await message.reply_text("❌ Aap is channel se banned ho. Bot use nahi kar sakte.")
            return 400

        # Agar already member / admin / creator hai -> allowed
        return 200

    except UserNotParticipant:
        # User channel me join nahi hai
        join_button = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📢 JOIN UPDATE CHANNEL",
                        url=f"https://t.me/{str(chat_id).replace('-100', '').replace('@', '')}"
                    )
                ],
                [
                    InlineKeyboardButton("✅ JOIN KAR LIYA", callback_data="check_fsub")
                ]
            ]
        )

        await message.reply_text(
            "⚠️ **Pehle hamara update channel join karo**\n\n"
            "📢 `@Ethicals_hacking`\n\n"
            "Phir dobara command ya link bhejna.",
            reply_markup=join_button
        )
        return 400

    except Exception as e:
        # Agar koi unexpected error aaye, to fsub skip kar dete hain
        print(f"[ForceSub Error] {e}")
        return 200
