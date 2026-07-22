from pyrogram.enums import ParseMode, ChatMembersFilter, ChatMemberStatus
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from SHUKLAMUSIC import app
from SHUKLAMUSIC.utils.database import is_on_off
from config import LOGGER_ID


async def play_logs(message, streamtype):
    if await is_on_off(2):
        try:
            query = message.text.split(None, 1)[1]
        except:
            query = "Link/File or Reply"

        try:
            members_count = await app.get_chat_members_count(message.chat.id)
        except:
            members_count = "Unknown"

        chat_link = None
        if message.chat.username:
            chat_link = f"https://t.me/{message.chat.username}"
        else:
            try:
                chat_link = await app.export_chat_invite_link(message.chat.id)
            except:
                pass

        logger_text = f"""
<blockquote>🎵 <b>PLAY LOG</b>

• <b>Request By :</b> {message.from_user.mention}
• <b>Query :</b> {query}
• <b>Chat :</b> {message.chat.title}
• <b>Chat ID :</b> <code>{message.chat.id}</code>
• <b>Members :</b> {members_count}</blockquote>
"""

        reply_markup = None
        if chat_link:
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 Group Link", url=chat_link)]]
            )

        if message.chat.id != LOGGER_ID:
            try:
                await app.send_message(
                    chat_id=LOGGER_ID,
                    text=logger_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup,
                )
            except:
                pass


async def bot_removed_logs(client, message, is_clone=False):
    if is_clone:
        return

    try:
        if message.from_user:
            kicked_by = message.from_user.mention
        else:
            kicked_by = "Unknown User"

        try:
            members_count = await client.get_chat_members_count(message.chat.id)
        except:
            members_count = "Unknown"

        chat_link = None
        if message.chat.username:
            chat_link = f"https://t.me/{message.chat.username}"

        remove_log_text = f"""
<blockquote>⚠️ <b>BOT REMOVED</b>

• <b>Removed By :</b> {kicked_by}
• <b>Chat :</b> {message.chat.title}
• <b>Chat ID :</b> <code>{message.chat.id}</code>
• <b>Members :</b> {members_count}</blockquote>
"""

        reply_markup = None
        if chat_link:
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 Group Link", url=chat_link)]]
            )

        await app.send_message(
            chat_id=LOGGER_ID,
            text=remove_log_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )

    except Exception as e:
        print(f"[ERROR] Remove Log Failed: {e}")


async def autoplay_log(client, chat_id, query):
    if not await is_on_off(2):
        return

    try:
        chat = await client.get_chat(chat_id)
        chat_title = chat.title
        chat_username = chat.username
    except:
        chat_title = "Unknown Chat"
        chat_username = None

    try:
        members_count = await client.get_chat_members_count(chat_id)
    except:
        members_count = "Unknown"

    # Owner Dhoondhne ka logic yahan add kiya gaya hai
    owner_name = "Unknown / Hidden"
    try:
        async for member in client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
            if member.status == ChatMemberStatus.OWNER:
                owner = member.user
                owner_name = f"{owner.first_name} {owner.last_name or ''}".strip()
                if owner.username:
                    owner_name += f" (@{owner.username})"
                break
    except:
        pass

    chat_link = None
    if chat_username:
        chat_link = f"https://t.me/{chat_username}"
    else:
        try:
            chat_link = await client.export_chat_invite_link(chat_id)
        except:
            pass

    logger_text = f"""
<blockquote>🔄 <b>AUTOPLAY LOG</b>

• <b>Track :</b> {query}
• <b>Triggered By :</b> Autoplay System
• <b>Chat :</b> {chat_title}
• <b>Chat ID :</b> <code>{chat_id}</code>
• <b>Owner :</b> {owner_name}
• <b>Members :</b> {members_count}</blockquote>
"""

    reply_markup = None
    if chat_link:
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 Group Link", url=chat_link)]]
        )

    try:
        await app.send_message(
            chat_id=LOGGER_ID,
            text=logger_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=reply_markup,
        )
    except Exception as e:
        print(f"[ERROR] Autoplay Log Failed: {e}")