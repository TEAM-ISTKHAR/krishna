from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from SHUKLAMUSIC import app
from SHUKLAMUSIC.utils.database import is_on_off
from config import LOGGER_ID


async def play_logs(message, streamtype):
    if await is_on_off(2):
        # Error se bachne ke liye query handle kar di
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

        # Username aur chat username ko handle kiya taaki 'None' show na kare
        chat_username = f"@{message.chat.username}" if message.chat.username else "Private Group 🔒"
        user_username = f"@{message.from_user.username}" if message.from_user.username else "No Username"

        # Blockquote ke sath tera same design
        logger_text = f"""<blockquote><b>❖ {app.mention} ᴘʟᴀʏ ʟᴏɢ</b>

<b>● ᴄʜᴀᴛ ɪᴅ ➠</b> <code>{message.chat.id}</code>
<b>● ᴄʜᴀᴛ ɴᴀᴍᴇ ➠</b> {message.chat.title}
<b>● ᴄʜᴀᴛ ᴜsᴇʀɴᴀᴍᴇ ➠</b> {chat_username}

<b>● ᴜsᴇʀ ɪᴅ ➠</b> <code>{message.from_user.id}</code>
<b>● ɴᴀᴍᴇ ➠</b> {message.from_user.mention}
<b>● ᴜsᴇʀɴᴀᴍᴇ ➠</b> {user_username}

<b>● ǫᴜᴇʀʏ ➠</b> {query}
<b>● sᴛʀᴇᴀᴍᴛʏᴘᴇ ➠</b> {streamtype}</blockquote>"""

        # Link milne par Inline Button banayega
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
