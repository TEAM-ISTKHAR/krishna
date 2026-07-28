from pyrogram.enums import ParseMode, ChatMembersFilter, ChatMemberStatus
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from SHUKLAMUSIC import app
from SHUKLAMUSIC.utils.database import is_on_off
from config import LOGGER_ID


async def play_logs(message, streamtype):
    if await is_on_off(2):
        # Error se bachne ke liye query handle
        try:
            query = message.text.split(None, 1)[1]
        except:
            query = "Link/File or Reply"

        # Group link generate karne ka logic
        chat_link = None
        if message.chat.username:
            chat_link = f"https://t.me/{message.chat.username}"
        else:
            try:
                chat_link = await app.export_chat_invite_link(message.chat.id)
            except:
                pass

        # Username aur chat username ko handle kiya
        chat_username = f"@{message.chat.username}" if message.chat.username else "Private Group 🔒"
        user_username = f"@{message.from_user.username}" if message.from_user.username else "No Username"

        logger_text = f"""<blockquote><b>❖ {app.mention} ᴘʟᴀʏ ʟᴏɢ</b>

<b>● ᴄʜᴀᴛ ɪᴅ ➠</b> <code>{message.chat.id}</code>
<b>● ᴄʜᴀᴛ ɴᴀᴍᴇ ➠</b> {message.chat.title}
<b>● ᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ ➠</b> {chat_username}

<b>● ᴜsᴇʀ ɪᴅ ➠</b> <code>{message.from_user.id}</code>
<b>● ɴᴀᴍᴇ ➠</b> {message.from_user.mention}
<b>● ᴜsᴇʀɴᴀᴍᴇ ➠</b> {user_username}

<b>● ǫᴜᴇʀʏ ➠</b> {query}
<b>● sᴛʀᴇᴀᴍᴛʏᴘᴇ ➠</b> {streamtype}</blockquote>"""

        reply_markup = None
        if chat_link:
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔗 ɢʀᴏᴜᴘ ʟɪɴᴋ", url=chat_link)]]
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
        return


async def autoplay_log(client, chat_id, query):
    if not await is_on_off(2):
        return

    try:
        chat = await client.get_chat(chat_id)
        chat_title = chat.title
        chat_username_str = f"@{chat.username}" if chat.username else "Private Group 🔒"
    except:
        chat_title = "Unknown Chat"
        chat_username_str = "Private Group 🔒"
        chat = None

    owner_id = "Unknown"
    owner_name = "Unknown / Hidden"
    owner_username = "No Username"
    try:
        async for member in client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
            if member.status == ChatMemberStatus.OWNER:
                owner = member.user
                owner_id = owner.id
                owner_name = owner.mention
                owner_username = f"@{owner.username}" if owner.username else "No Username"
                break
    except:
        pass

    chat_link = None
    if chat and chat.username:
        chat_link = f"https://t.me/{chat.username}"
    else:
        try:
            chat_link = await client.export_chat_invite_link(chat_id)
        except:
            pass

    logger_text = f"""<blockquote><b>❖ {app.mention} ᴀᴜᴛᴏᴘʟᴀʏ ʟᴏɢ</b>

<b>● ᴄʜᴀᴛ ɪᴅ ➠</b> <code>{chat_id}</code>
<b>● ᴄʜᴀᴛ ɴᴀᴍᴇ ➠</b> {chat_title}
<b>● ᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ ➠</b> {chat_username_str}

<b>● ᴏᴡɴᴇʀ ɪᴅ ➠</b> <code>{owner_id}</code>
<b>● ᴏᴡɴᴇʀ ɴᴀᴍᴇ ➠</b> {owner_name}
<b>● ᴏᴡɴᴇʀ ᴜsᴇʀɴᴀᴍᴇ ➠</b> {owner_username}

<b>● ǫᴜᴇʀʏ ➠</b> {query}
<b>● sᴛʀᴇᴀᴍᴛʏᴘᴇ ➠</b> ᴀᴜᴛᴏᴘʟᴀʏ</blockquote>"""

    reply_markup = None
    if chat_link:
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔗 ɢʀᴏᴜᴘ ʟɪɴᴋ", url=chat_link)]]
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
