from pyrogram.enums import ButtonStyle, ParseMode
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
)

from Music import app


# ==========================================================
# GUEST MESSAGE
# ==========================================================

# Stylish font added, wrapped in <b> tags for bigger size, 
# along with blockquote and clickable bot name.
ADD_ME_PROMO_TEXT = (
    "❖ <a href=\"https://t.me/{username}\">˹{name}˼ ♪</a> — <b>𝖸𝗈𝗎𝗋 𝖯𝗋𝖾𝗆𝗂𝗎𝗆 𝖬𝗎𝗌𝗂𝖼 𝖲𝗍𝗋𝖾𝖺𝗆𝖾𝗋 𝖡𝗈𝗍 🎶</b>\n\n"
    
    "<blockquote><b>▸ 𝖥𝖺𝗌𝗍 • 𝖫𝖺𝗀 𝖥𝗋𝖾𝖾 • 𝖭𝗈 𝖠𝖽𝗌 🍃</b>\n"
    "<b>▸ 𝖠𝗎𝗍𝗈-𝖯𝗅𝖺𝗒 • 𝖠𝗎𝖽𝗂𝗈 • 𝖵𝗂𝖽𝖾𝗈 🎥</b></blockquote>\n\n"
    
    "<b>➜ 𝖠𝖽𝖽</b> <a href=\"https://t.me/{username}\">˹{name}˼ ♪</a> <b>𝖳𝗈 𝖸𝗈𝗎𝗋 𝖦𝗋𝗈𝗎𝗉 & 𝖤𝗇𝗃𝗈𝗒 𝖧𝗂𝗀𝗁 𝖰𝗎𝖺𝗅𝗂𝗍𝗒 𝖲𝗈𝗇𝗀𝗌 🎶</b>"
)


# ==========================================================
# BUTTONS
# ==========================================================

def _add_me_markup(username: str):

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text="➕ Add Me In Your Group",
                    url=f"https://t.me/{username}?startgroup=true",
                    style=ButtonStyle.SUCCESS,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎶 Open Music Bot",
                    url=f"https://t.me/{username}",
                    style=ButtonStyle.PRIMARY,
                )
            ],
        ]
    )


# ==========================================================
# GUEST MODE
# ==========================================================

@app.on_guest_message()
async def guest_username_mention(_, message: Message):

    guest_query_id = getattr(
        message,
        "guest_query_id",
        None,
    )

    if not guest_query_id:
        return

    try:

        # --------------------------------------------------
        # GET BOT INFORMATION 
        # --------------------------------------------------

        me = await app.get_me()

        # Full bot name 
        name = me.first_name or "Music Bot"

        if me.last_name:
            name = f"{name} {me.last_name}"

        # Bot username
        username = me.username

        if not username:
            return

        # --------------------------------------------------
        # CREATE MESSAGE
        # --------------------------------------------------

        promo_text = ADD_ME_PROMO_TEXT.format(
            name=name,
            username=username,
        )

        # --------------------------------------------------
        # KEYBOARD
        # --------------------------------------------------

        keyboard = _add_me_markup(username)

        # --------------------------------------------------
        # INLINE RESULT
        # --------------------------------------------------

        result = InlineQueryResultArticle(
            title=f"❖ {name} ♪",
            description=f"@{username} • Add Me In Your Group 🎶",
            thumb_url="https://files.catbox.moe/qv2ob4.jpg",

            input_message_content=InputTextMessageContent(
                message_text=promo_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            ),

            reply_markup=keyboard,
        )

        # --------------------------------------------------
        # ANSWER GUEST QUERY
        # --------------------------------------------------

        await app.answer_guest_query(
            guest_query_id,
            result=result,
        )

    except Exception as e:

        print(
            f"Guest Mode Error: {type(e).__name__}: {e}"
        )
