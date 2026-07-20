import random
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.errors import MessageNotModified

from SHUKLAMUSIC import app
from SHUKLAMUSIC.utils.database import get_autoplay, set_autoplay
from SHUKLAMUSIC.utils.decorators import AdminRightsCheck
from config import BANNED_USERS

PHOTO_URL = "https://files.catbox.moe/6r97s4.jpg"

def get_panel(chat_id, enabled):
    status = "🟢 𝐄ɴᴀʙʟᴇᴅ" if enabled else "🔴 𝐃ɪsᴀʙʟᴇᴅ"

    caption = f"""
**🎵 𝐀ᴜᴛᴏ 𝐏ʟᴀʏ 𝐒ᴇᴛᴛɪɴɢ𝐬**

➻ 𝐌ᴀɴᴀɢᴇ 𝐀ᴜᴛᴏ 𝐏ʟᴀʏ ғᴇᴀᴛᴜʀᴇ ғᴏʀ ᴛʜɪs ɢʀᴏᴜᴘ.

**✦ 𝐂ᴜʀʀᴇɴᴛ 𝐒ᴛᴀᴛᴜ𝐬**
{status}

━━━━━━━━━━━━━━━
⚡ 𝐏ᴏᴡᴇʀᴇᴅ ʙʏ ➛ 𝐁ᴇᴛᴀ𝐁ᴏᴛ𝐬
"""

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "𝐄ɴᴀʙʟᴇ",
                    callback_data=f"AUTOPLAY_ENABLE|{chat_id}",
                ),
                InlineKeyboardButton(
                    "𝐃ɪsᴀʙʟᴇ",
                    callback_data=f"AUTOPLAY_DISABLE|{chat_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"𝐀ᴜᴛᴏ 𝐏ʟᴀʏ : {status}",
                    callback_data="AUTOPLAY_STATUS",
                )
            ],
        ]
    )

    return caption, buttons


@app.on_message(
    filters.command(["autoplay"])
    & filters.group
    & ~BANNED_USERS
)
@AdminRightsCheck
async def autoplay_mode(client, message: Message, _, chat_id):
    # Using the exact function we added in database.py earlier
    enabled = await get_autoplay(chat_id)
    caption, buttons = get_panel(chat_id, enabled)

    await message.reply_photo(
        photo=PHOTO_URL,
        caption=caption,
        reply_markup=buttons,
    )


@app.on_callback_query(filters.regex("^AUTOPLAY_ENABLE") & ~BANNED_USERS)
async def autoplay_enable(_, query: CallbackQuery):
    chat_id = int(query.data.split("|")[1])

    # Checking admin rights
    member = await app.get_chat_member(chat_id, query.from_user.id)
    if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        return await query.answer("❌ You must be an admin to change this setting!", show_alert=True)

    # Set autoplay to True
    await set_autoplay(chat_id, True)
    caption, buttons = get_panel(chat_id, True)

    try:
        await query.message.edit_caption(
            caption=caption,
            reply_markup=buttons,
        )
    except MessageNotModified:
        pass

    await query.answer("Auto Play Enabled ✅")


@app.on_callback_query(filters.regex("^AUTOPLAY_DISABLE") & ~BANNED_USERS)
async def autoplay_disable(_, query: CallbackQuery):
    chat_id = int(query.data.split("|")[1])

    # Checking admin rights
    member = await app.get_chat_member(chat_id, query.from_user.id)
    if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
        return await query.answer("❌ You must be an admin to change this setting!", show_alert=True)

    # Set autoplay to False
    await set_autoplay(chat_id, False)
    caption, buttons = get_panel(chat_id, False)

    try:
        await query.message.edit_caption(
            caption=caption,
            reply_markup=buttons,
        )
    except MessageNotModified:
        pass

    await query.answer("Auto Play Disabled ❌")


@app.on_callback_query(filters.regex("^AUTOPLAY_STATUS"))
async def autoplay_status(_, query: CallbackQuery):
    await query.answer(
        "Auto Play Status Panel",
        show_alert=False,
    )
