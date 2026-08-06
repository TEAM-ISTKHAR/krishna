# -----------------------------------------------
# 🔸 Pure AI ChatBot (Smart & Human-like)
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
        return await message.reply_text("⚠️ **Only group admins can use this command.**")
    
    is_on = await is_chatbot_enabled(message.chat.id)
    status_text = "🟢 **𝗔𝗖𝗧𝗜𝗩𝗘** ✨" if is_on else "🔴 **𝗗𝗜𝗦𝗔𝗕𝗟𝗘𝗗** 💤"
    
    # Premium Button UI
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✨ 𝗘𝗡𝗔𝗕𝗟𝗘 ✨", callback_data="cb_on"),
            InlineKeyboardButton("🛑 𝗗𝗜𝗦𝗔𝗕𝗟𝗘 🛑", callback_data="cb_off")
        ]
    ])
    
    await message.reply_text(
        f"🤖 **𝗜𝗻𝘁𝗲𝗹𝗹𝗶𝗴𝗲𝗻𝘁 𝗖𝗵𝗮𝘁𝗕𝗼𝘁 𝗦𝗲𝘁𝘁𝗶𝗻𝗴𝘀**\n\n"
        f"**𝗖𝘂𝗿𝗿𝗲𝗻𝘁 𝗦𝘁𝗮𝘁𝘂𝘀:** {status_text}\n\n"
        f"⚡ _Manage the AI chatbot for this group using the buttons below:_ ⚡",
        reply_markup=keyboard
    )

@app.on_callback_query(filters.regex(r"^cb_(on|off)$") & ~BANNED_USERS)
async def chatbot_callback(client, query: CallbackQuery):
    if not await is_admin(query.message.chat.id, query.from_user.id):
        return await query.answer("⚠️ Admin rights required to change this setting.", show_alert=True)

    action = query.data.split("_")[1]
    
    if action == "on":
        await set_chatbot_enabled(query.message.chat.id, True)
        await query.message.edit_text("✅ **ChatBot Successfully Enabled!** ✨\n_I am now active and ready to chat._ 💬")
    else:
        await set_chatbot_enabled(query.message.chat.id, False)
        await query.message.edit_text("💤 **ChatBot Successfully Disabled.** 🛑\n_I will ignore all messages in this group._")
        
    await query.answer("Settings Updated Successfully! ✨")


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
        # Show typing status for realistic feel
        await app.send_chat_action(message.chat.id, enums.ChatAction.TYPING)
        
        # Smart, Friendly, Human-like Personality Prompt
        system_prompt = (
            "You are a smart, friendly, and highly engaging Telegram group member from India. "
            "Your tone adapts based on the user: be funny and casual with friendly messages, professional if asked technical questions, and empathetic if the user is sad. "
            "Talk naturally in Hinglish (Hindi + English) or pure Hindi/English depending on context. "
            "Use premium, expressive emojis naturally like ✨, 😅, 💯, 🔥, ❤️. "
            "NEVER say you are an AI, bot, language model, or assistant. Act like a real human friend. "
            "If someone asks who your owner is, say 'My owner is my developer ItzShukla'. "
            "Keep your replies strictly concise (1-2 lines) and avoid robotic or repetitive language."
        )

        # Call OpenAI / OpenRouter API
        response = await ai_client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message.text}
            ],
            max_tokens=50,    # Message short rakhne ke liye
            temperature=0.8   # Natural human-like randomness
        )
        
        ai_reply = response.choices[0].message.content
        
        if ai_reply:
            await message.reply_text(ai_reply)
            
    except Exception as e:
        print(f"AI Chatbot Error: {e}")
