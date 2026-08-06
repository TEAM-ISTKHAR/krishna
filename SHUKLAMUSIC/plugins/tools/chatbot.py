# -----------------------------------------------
# 🔸 StrangerMusic Project — MongoDB + AI ChatBot
# 🔹 Keyword-trained auto-reply + OpenAI/OpenRouter API Fallback
# -----------------------------------------------
import re
from pyrogram import filters
from pyrogram.types import Message
from pyrogram import enums

from openai import AsyncOpenAI

from SHUKLAMUSIC import app
from SHUKLAMUSIC.core.mongo import mongodb
from SHUKLAMUSIC.utils.database import is_nonadmin_chat
from SHUKLAMUSIC.misc import SUDOERS
from config import BANNED_USERS, OWNER_ID

chatbot_settings = mongodb.chatbot_settings
chatbot_replies = mongodb.chatbot_replies

# --- AI API Configuration ---
OPENAI_API_KEY = "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"

# Using OpenRouter base_url since the key starts with 'sk-or-'. 
# Remove base_url if you switch to a standard OpenAI key.
ai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://openrouter.ai/api/v1" 
)
# ----------------------------

_E_ON = 6073371665381724173     # 🥰 emoji_2e47b
_E_OFF = 6073598306510967017    # 🐈 emoji_2e47b
_E_LEARN = 6073117703965511893  # 💐 emoji_2e47b
_E_ERR = 5978715546865112655    # 🚩


def e(eid, fb):
    return f"<emoji id={eid}>{fb}</emoji>"


CB_HELP = f"""
{e(_E_LEARN,'💐')} <b>ChatBot — Command List</b>

An auto-reply chatbot powered by MongoDB for custom keywords, with an AI API fallback for natural conversations.

• <code>/chatbot on</code> — enable auto-replies in this chat
• <code>/chatbot off</code> — disable auto-replies in this chat
• <code>/teach &lt;keyword&gt; | &lt;reply&gt;</code> — teach the bot a new reply (admin only)
• <code>/unlearn &lt;keyword&gt;</code> — remove a taught reply (admin only)
• <code>/learned</code> — list everything the bot has learned in this chat
"""


async def is_chatbot_enabled(chat_id: int) -> bool:
    doc = await chatbot_settings.find_one({"chat_id": chat_id})
    return bool(doc and doc.get("enabled"))


async def set_chatbot_enabled(chat_id: int, enabled: bool):
    await chatbot_settings.update_one({"chat_id": chat_id}, {"$set": {"enabled": enabled}}, upsert=True)


async def is_admin(client, message: Message) -> bool:
    if message.sender_chat and message.sender_chat.id == message.chat.id:
        return True
    if not message.from_user:
        return False
    user_id = message.from_user.id
    try:
        if user_id in SUDOERS or str(user_id) == str(OWNER_ID):
            return True
    except Exception:
        pass
    try:
        member = await client.get_chat_member(message.chat.id, user_id)
        return member.status in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER)
    except Exception:
        return False


@app.on_message(filters.command("chatbothelp") & ~BANNED_USERS)
async def chatbot_help_cmd(client, message: Message):
    await message.reply_text(CB_HELP)


@app.on_message(filters.command("chatbot") & filters.group & ~BANNED_USERS)
async def chatbot_toggle_cmd(client, message: Message):
    if len(message.command) != 2 or message.command[1].lower() not in ("on", "off"):
        state = await is_chatbot_enabled(message.chat.id)
        status = f"{e(_E_ON,'🥰')} <b>ON</b>" if state else f"{e(_E_OFF,'🐈')} <b>OFF</b>"
        return await message.reply_text(
            f"{e(_E_LEARN,'💐')} <b>ChatBot status:</b> {status}\n\nUsage: <code>/chatbot on</code> or <code>/chatbot off</code>"
        )
    if not await is_admin(client, message):
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Only group admins can toggle the chatbot.")
    state = message.command[1].lower() == "on"
    await set_chatbot_enabled(message.chat.id, state)
    if state:
        await message.reply_text(f"{e(_E_ON,'🥰')} <b>ChatBot enabled</b> — I will now auto-reply (using AI & keywords) in this chat.")
    else:
        await message.reply_text(f"{e(_E_OFF,'🐈')} <b>ChatBot disabled</b> for this chat.")


@app.on_message(filters.command("teach") & filters.group & ~BANNED_USERS)
async def teach_cmd(client, message: Message):
    if not await is_admin(client, message):
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Only group admins can teach the chatbot.")
    if len(message.command) < 2 or "|" not in message.text:
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Usage: <code>/teach keyword | reply text</code>")
    raw = message.text.split(None, 1)[1]
    if "|" not in raw:
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Usage: <code>/teach keyword | reply text</code>")
    keyword, reply = raw.split("|", 1)
    keyword = keyword.strip().lower()
    reply = reply.strip()
    if not keyword or not reply:
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Both keyword and reply are required.")
    await chatbot_replies.update_one(
        {"chat_id": message.chat.id, "keyword": keyword},
        {"$set": {"reply": reply}},
        upsert=True,
    )
    await message.reply_text(f"{e(_E_LEARN,'💐')} Learned! When someone says <b>{keyword}</b>, I'll reply with that text.")


@app.on_message(filters.command("unlearn") & filters.group & ~BANNED_USERS)
async def unlearn_cmd(client, message: Message):
    if not await is_admin(client, message):
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Only group admins can do this.")
    if len(message.command) < 2:
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Usage: <code>/unlearn keyword</code>")
    keyword = message.text.split(None, 1)[1].strip().lower()
    result = await chatbot_replies.delete_one({"chat_id": message.chat.id, "keyword": keyword})
    if result.deleted_count:
        await message.reply_text(f"{e(_E_ON,'🥰')} Forgot the reply for <b>{keyword}</b>.")
    else:
        await message.reply_text(f"{e(_E_ERR,'🚩')} No learned reply found for that keyword.")


@app.on_message(filters.command("learned") & filters.group & ~BANNED_USERS)
async def learned_cmd(client, message: Message):
    cursor = chatbot_replies.find({"chat_id": message.chat.id}).limit(50)
    keywords = [doc["keyword"] async for doc in cursor]
    if not keywords:
        return await message.reply_text("I haven't learned any custom keywords in this chat yet. Teach me with /teach.")
    text = f"{e(_E_LEARN,'💐')} <b>Learned keywords in this chat:</b>\n\n" + ", ".join(f"<code>{k}</code>" for k in keywords)
    await message.reply_text(text)


@app.on_message(filters.group & filters.text & ~filters.bot & ~filters.command(["teach", "unlearn", "learned", "chatbot", "chatbothelp"]) & ~BANNED_USERS, group=20)
async def chatbot_auto_reply(client, message: Message):
    if not message.text or message.text.startswith("/"):
        return
    if not await is_chatbot_enabled(message.chat.id):
        return
    
    text = message.text.strip().lower()
    text_clean = re.sub(r"[^\w\s]", "", text)

    # 1. Check for custom learned keywords in MongoDB first
    doc = await chatbot_replies.find_one({"chat_id": message.chat.id, "keyword": text})
    if not doc:
        doc = await chatbot_replies.find_one({"chat_id": message.chat.id, "keyword": text_clean})
    if not doc:
        cursor = chatbot_replies.find({"chat_id": message.chat.id})
        async for candidate in cursor:
            if candidate["keyword"] in text_clean.split() or candidate["keyword"] in text_clean:
                doc = candidate
                break
    
    # If custom keyword is found, reply and exit
    if doc:
        try:
            return await message.reply_text(doc["reply"])
        except Exception:
            return

    # 2. AI Fallback: Generate response using OpenAI / OpenRouter API
    # To prevent spam and API drain, you might want to restrict this to replies to the bot
    # If you want it to reply to EVERYTHING, leave it as is.
    try:
        await app.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
        
        response = await ai_client.chat.completions.create(
            model="openai/gpt-3.5-turbo", # OpenRouter model naming format. Change to "gpt-3.5-turbo" if using official OpenAI.
            messages=[
                {"role": "system", "content": "You are a helpful, friendly, and concise AI assistant participating in a Telegram group chat."},
                {"role": "user", "content": message.text}
            ],
            max_tokens=150 # Keeping responses relatively short for group chats
        )
        
        ai_reply = response.choices[0].message.content
        if ai_reply:
            await message.reply_text(ai_reply)
            
    except Exception as e:
        # Silently pass or print error if API fails (e.g., rate limit, invalid key)
        print(f"AI Chatbot Error: {e}")
        


async def is_chatbot_enabled(chat_id: int) -> bool:
    doc = await chatbot_settings.find_one({"chat_id": chat_id})
    return bool(doc and doc.get("enabled"))


async def set_chatbot_enabled(chat_id: int, enabled: bool):
    await chatbot_settings.update_one({"chat_id": chat_id}, {"$set": {"enabled": enabled}}, upsert=True)


async def is_admin(client, message: Message) -> bool:
    if message.sender_chat and message.sender_chat.id == message.chat.id:
        return True
    if not message.from_user:
        return False
    user_id = message.from_user.id
    try:
        if user_id in SUDOERS or str(user_id) == str(OWNER_ID):
            return True
    except Exception:
        pass
    try:
        member = await client.get_chat_member(message.chat.id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


@app.on_message(filters.command("chatbothelp") & ~BANNED_USERS)
async def chatbot_help_cmd(client, message: Message):
    await message.reply_text(CB_HELP)


@app.on_message(filters.command("chatbot") & filters.group & ~BANNED_USERS)
async def chatbot_toggle_cmd(client, message: Message):
    if len(message.command) != 2 or message.command[1].lower() not in ("on", "off"):
        state = await is_chatbot_enabled(message.chat.id)
        status = f"{e(_E_ON,'🥰')} <b>ON</b>" if state else f"{e(_E_OFF,'🐈')} <b>OFF</b>"
        return await message.reply_text(
            f"{e(_E_LEARN,'💐')} <b>ChatBot status:</b> {status}\n\nUsage: <code>/chatbot on</code> or <code>/chatbot off</code>"
        )
    if not await is_admin(client, message):
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Only group admins can toggle the chatbot.")
    state = message.command[1].lower() == "on"
    await set_chatbot_enabled(message.chat.id, state)
    if state:
        await message.reply_text(f"{e(_E_ON,'🥰')} <b>ChatBot enabled</b> — I will now auto-reply to learned keywords in this chat.")
    else:
        await message.reply_text(f"{e(_E_OFF,'🐈')} <b>ChatBot disabled</b> for this chat.")


@app.on_message(filters.command("teach") & filters.group & ~BANNED_USERS)
async def teach_cmd(client, message: Message):
    if not await is_admin(client, message):
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Only group admins can teach the chatbot.")
    if len(message.command) < 2 or "|" not in message.text:
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Usage: <code>/teach keyword | reply text</code>")
    raw = message.text.split(None, 1)[1]
    if "|" not in raw:
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Usage: <code>/teach keyword | reply text</code>")
    keyword, reply = raw.split("|", 1)
    keyword = keyword.strip().lower()
    reply = reply.strip()
    if not keyword or not reply:
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Both keyword and reply are required.")
    await chatbot_replies.update_one(
        {"chat_id": message.chat.id, "keyword": keyword},
        {"$set": {"reply": reply}},
        upsert=True,
    )
    await message.reply_text(f"{e(_E_LEARN,'💐')} Learned! When someone says <b>{keyword}</b>, I'll reply with that text.")


@app.on_message(filters.command("unlearn") & filters.group & ~BANNED_USERS)
async def unlearn_cmd(client, message: Message):
    if not await is_admin(client, message):
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Only group admins can do this.")
    if len(message.command) < 2:
        return await message.reply_text(f"{e(_E_ERR,'🚩')} Usage: <code>/unlearn keyword</code>")
    keyword = message.text.split(None, 1)[1].strip().lower()
    result = await chatbot_replies.delete_one({"chat_id": message.chat.id, "keyword": keyword})
    if result.deleted_count:
        await message.reply_text(f"{e(_E_ON,'🥰')} Forgot the reply for <b>{keyword}</b>.")
    else:
        await message.reply_text(f"{e(_E_ERR,'🚩')} No learned reply found for that keyword.")


@app.on_message(filters.command("learned") & filters.group & ~BANNED_USERS)
async def learned_cmd(client, message: Message):
    cursor = chatbot_replies.find({"chat_id": message.chat.id}).limit(50)
    keywords = [doc["keyword"] async for doc in cursor]
    if not keywords:
        return await message.reply_text("I haven't learned anything in this chat yet. Teach me with /teach.")
    text = f"{e(_E_LEARN,'💐')} <b>Learned keywords in this chat:</b>\n\n" + ", ".join(f"<code>{k}</code>" for k in keywords)
    await message.reply_text(text)


@app.on_message(filters.group & filters.text & ~filters.bot & ~filters.command(["teach", "unlearn", "learned", "chatbot"]) & ~BANNED_USERS, group=20)
async def chatbot_auto_reply(client, message: Message):
    if not message.text or message.text.startswith("/"):
        return
    if not await is_chatbot_enabled(message.chat.id):
        return
    text = message.text.strip().lower()
    text_clean = re.sub(r"[^\w\s]", "", text)

    doc = await chatbot_replies.find_one({"chat_id": message.chat.id, "keyword": text})
    if not doc:
        doc = await chatbot_replies.find_one({"chat_id": message.chat.id, "keyword": text_clean})
    if not doc:
        cursor = chatbot_replies.find({"chat_id": message.chat.id})
        async for candidate in cursor:
            if candidate["keyword"] in text_clean.split() or candidate["keyword"] in text_clean:
                doc = candidate
                break
    if doc:
        try:
            await message.reply_text(doc["reply"])
        except Exception:
            pass
