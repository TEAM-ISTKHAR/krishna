# -----------------------------------------------
# 🔸 Pure AI Tsundere ChatBot (No Manual Keywords)
# 🔹 Powered by OpenAI/OpenRouter API
# -----------------------------------------------
import re
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import enums

from openai import AsyncOpenAI

from SHUKLAMUSIC import app
from SHUKLAMUSIC.core.mongo import mongodb
from SHUKLAMUSIC.misc import SUDOERS
from config import BANNED_USERS, OWNER_ID

# Sirf ON/OFF ka data save karne ke liye Mongo use hoga
chatbot_settings = mongodb.chatbot_settings

# --- AI API Configuration ---
OPENAI_API_KEY = "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"

ai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://openrouter.ai/api/v1" 
)

# --- Helper Functions ---
async def is_chatbot_enabled(chat_id: int) -> bool:
    doc = await chatbot_settings.find_one({"chat_id": chat_id})
    return bool(doc and doc.get("enabled"))

async def set_chatbot_enabled(chat_id: int, enabled: bool):
    await chatbot_settings.update_one({"chat_id": chat_id}, {"$set": {"enabled": enabled}}, upsert=True)

async def is_admin(chat_id: int, user_id: int) -> bool:
    try:
        if user_id in SUDOERS or str(user_id) == str(OWNER_ID):
            return True
        member = await app.get_chat_member(chat_id, user_id)
        return member.status in (enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER)
    except Exception:
        return False

# -----------------------------------------------
# 🎛️ COMMANDS & BUTTONS (ON/OFF)
# -----------------------------------------------

@app.on_message(filters.command("chatbot") & filters.group & ~BANNED_USERS)
async def chatbot_menu(client, message: Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return await message.reply_text("🚩 Only group admins can use this command, Baka!")
    
    is_on = await is_chatbot_enabled(message.chat.id)
    status_text = "🟢 **ON**" if is_on else "🔴 **OFF**"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Turn ON", callback_data="cb_on"),
            InlineKeyboardButton("Turn OFF", callback_data="cb_off")
        ]
    ])
    
    await message.reply_text(
        f"🤖 **Baka ChatBot Settings**\n\n"
        f"**Current Status:** {status_text}\n\n"
        f"Choose an option below:",
        reply_markup=keyboard
    )

@app.on_callback_query(filters.regex(r"^cb_(on|off)$") & ~BANNED_USERS)
async def chatbot_callback(client, query: CallbackQuery):
    if not await is_admin(query.message.chat.id, query.from_user.id):
        return await query.answer("Huh! Only admins can touch my settings, Baka!", show_alert=True)

    action = query.data.split("_")[1]
    
    if action == "on":
        await set_chatbot_enabled(query.message.chat.id, True)
        await query.message.edit_text("✅ **Baka ChatBot is now ENABLED!**\nGet ready for some attitude! 💅")
    else:
        await set_chatbot_enabled(query.message.chat.id, False)
        await query.message.edit_text("💤 **Baka ChatBot is DISABLED.**\nFine, I didn't want to talk to you anyway! 😤")
        
    await query.answer("Settings Updated!")


# -----------------------------------------------
# 🗣️ MAIN AI CHAT LOGIC
# -----------------------------------------------

@app.on_message(filters.group & filters.text & ~filters.bot & ~filters.command(["chatbot"]) & ~BANNED_USERS, group=20)
async def chatbot_auto_reply(client, message: Message):
    # Ignore commands or prefixes
    if not message.text or message.text.startswith(("/", "!", "?", ".")):
        return
    
    # Check if chatbot is ON in this group
    if not await is_chatbot_enabled(message.chat.id):
        return

    try:
        # Show typing status
        await app.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
        
        # Baka Bot System Prompt
        system_prompt = (
            "You are a Tsundere anime-style Telegram group member from India. "
            "Always reply in very short, casual Hinglish (Hindi + English). "
            "You have a tsundere personality: act slightly annoyed, bossy, and always use words like 'Baka', 'Huh', 'Duffer', or 'Chup kar'. "
            "Never be too sweet directly, but show you care deep down. "
            "Use emojis like 🙄, 😤, 💢, 🤨, 💅. "
            "NEVER say you are an AI, bot, or assistant. NEVER be overly polite. "
            "If someone asks who your owner is, say 'My owner is my developer, Baka!'. "
            "Keep your replies strictly to 1 short line."
        )

        # Call OpenAI / OpenRouter API
        response = await ai_client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message.text}
            ],
            max_tokens=40,    # Keeps replies short
            temperature=0.85  # Attitude variations
        )
        
        ai_reply = response.choices[0].message.content
        
        if ai_reply:
            await message.reply_text(ai_reply)
            
    except Exception as e:
        print(f"AI Chatbot Error: {e}")
