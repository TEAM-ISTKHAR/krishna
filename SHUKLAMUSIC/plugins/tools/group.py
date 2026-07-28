import re
import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from SHUKLAMUSIC import app
from config import OWNER_ID


# vc started
@app.on_message(filters.video_chat_started)
async def brah(_, msg):
    await msg.reply("ᴠᴏɪᴄᴇ ᴄʜᴀᴛ sᴛᴀʀᴛᴇᴅ")


# vc ended
@app.on_message(filters.video_chat_ended)
async def brah2(_, msg):
    await msg.reply("**ᴠᴏɪᴄᴇ ᴄʜᴀᴛ ᴇɴᴅᴇᴅ**")


# invite members on vc
if hasattr(filters, "video_chat_participants_invited"):
    @app.on_message(filters.video_chat_participants_invited)
    async def brah3(_, message: Message):
        text = f"{message.from_user.mention} ɪɴᴠɪᴛᴇᴅ "
        for user in message.video_chat_participants_invited.users:
            try:
                text += f"[{user.first_name}](tg://user?id={user.id}) "
            except Exception:
                pass
        try:
            await message.reply(f"{text} 😉")
        except Exception:
            pass


@app.on_message(filters.command("math"))
async def calculate_math(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage:\n`/math 2+2`", quote=True)
    
    expression = message.text.split(None, 1)[1]
    
    # 🔥 SECURITY CHECK: Only allow numbers and basic math operators. No letters allowed!
    if not re.match(r'^[0-9\+\-\*\/\(\)\.\s]+$', expression):
        return await message.reply_text("❌ **Unsafe or invalid expression! Only numbers and basic math symbols are allowed.**", quote=True)
        
    try:
        # Safe eval execution to prevent remote code execution (RCE)
        result = eval(expression, {"__builtins__": None}, {})
        response = f"✅ **Result:** `{result}`"
    except ZeroDivisionError:
        response = "❌ **Error: Division by zero is not allowed.**"
    except Exception:
        response = "❌ **Invalid expression**"
        
    await message.reply_text(response, quote=True)


@app.on_message(filters.command("leavegroup") & filters.user(OWNER_ID))
async def bot_leave(_, message: Message):
    await message.reply_text("sᴜᴄᴄᴇssғᴜʟʟʏ ʟᴇғᴛ !!")
    await app.leave_chat(chat_id=message.chat.id, delete=True)


@app.on_message(filters.command(["spg"], ["/", "!", "."]))
async def search(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/spg <query>`", quote=True)

    query = message.text.split(None, 1)[1]
    msg = await message.reply("Searching...")
    start = 1

    async with aiohttp.ClientSession() as session:
        url = (
            f"https://content-customsearch.googleapis.com/customsearch/v1"
            f"?cx=ec8db9e1f9e41e65e&q={query}"
            f"&key=AIzaSyAa8yy0GdcGPHdtD083HiGGx_S0vMPScDM&start={start}"
        )
        async with session.get(url, headers={"x-referer": "https://explorer.apis.google.com"}) as r:
            response = await r.json()

    if not response.get("items"):
        return await msg.edit_text("No results found!")

    result = ""
    seen = set()
    for item in response["items"]:
        title = item["title"]
        link = item["link"]
        if "/s" in link:
            link = link.replace("/s", "")
        elif re.search(r"\/\d", link):
            link = re.sub(r"\/\d", "", link)
        if "?" in link:
            link = link.split("?")[0]
        if link in seen:
            continue
        seen.add(link)
        result += f"{title}\n{link}\n\n"

    next_btn = InlineKeyboardMarkup(
        [[InlineKeyboardButton("▶️ Next ▶️", callback_data=f"spg_next {start + 10} {query}")]]
    )
    await msg.edit_text(result, reply_markup=next_btn, disable_web_page_preview=True)
