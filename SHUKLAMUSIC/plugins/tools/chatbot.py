import re
import logging
from collections import defaultdict, deque
from pyrogram import filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from openai import AsyncOpenAI

from SHUKLAMUSIC import app
from SHUKLAMUSIC.core.mongo import mongodb
from SHUKLAMUSIC.misc import SUDOERS
from config import BANNED_USERS, OWNER_ID

# Setup basic logging for error handling
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sirf ON/OFF ka data save karne ke liye Mongo use hoga
chatbot_settings = mongodb.chatbot_settings

# --- AI API Configuration ---
OPENAI_API_KEY = "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"

ai_client = AsyncOpenAI(
    api_key=OPENAI_API_KEY,
    base_url="https://openrouter.ai/api/v1" 
)

# --- Conversation Memory ---
# Stores the last 8 messages per chat to maintain context without exceeding token limits
chat_history = defaultdict(lambda: deque(maxlen=8))

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
        # Clear memory when disabled to prevent stale context later
        chat_history.pop(query.message.chat.id, None)
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

    # Context formatting
    user_name = message.from_user.first_name if message.from_user else "User"
    is_reply_to_bot = False
    reply_context = ""

    # Check if the user is replying to someone
    if message.reply_to_message:
        replied_user = message.reply_to_message.from_user
        if replied_user:
            if replied_user.id == client.me.id:
                is_reply_to_bot = True
                reply_context = f"[Replying to YOU]: {message.reply_to_message.text}"
            else:
                reply_context = f"[Replying to {replied_user.first_name}]: {message.reply_to_message.text}"

    # Build the current message for memory
    current_msg = f"{user_name}: {message.text}"
    if reply_context:
        current_msg = f"{reply_context}\n{current_msg}"

    # Fetch group history
    history = chat_history[message.chat.id]
    history_text = "\n".join(history)

    # --------------------------------------------------------
    # STRICT HUMAN-LIKE SYSTEM PROMPT
    # --------------------------------------------------------
    system_prompt = f"""You are a regular person chatting in a Telegram group. Your developer is ItzShukla.
NEVER act like an AI, bot, or assistant. 

CRITICAL RULES:
1. MATCH LENGTH: If the user says 1-2 words ("Acha", "Hmm", "Haan", "Kya"), reply with 1-2 words (e.g., "haan", "😂", "hmm"). Do NOT write paragraphs for short messages.
2. NEVER FORCE CONVERSATION: Do NOT ask "Kya chal raha hai?", "Kaise ho?", or "Batao" unless genuinely necessary. If there's nothing to say, just react or say "hmm".
3. NO AI PHRASES: Never say "That's wonderful!", "I'm here to help", "As an AI", or give random motivational life advice.
4. EMOJI CONTROL: Use 0-1 emojis maximum. DO NOT use ✨, 🌟, 😊 constantly.
5. LANGUAGE: Use natural, casual Hinglish. Do not be perfectly grammatical.
6. WHEN TO IGNORE: If users are talking to each other and not to you, or if the message doesn't need a reply, output EXACTLY the word: IGNORE.

EXAMPLES:
User: Acha
You: Haan 😂 (OR) IGNORE

User: Hmm
You: 😌

User: kya
You: kuch nahi bhai

User: Zindagi ajeeb hai
You: kasam se 😂

Recent Chat History (for context):
{history_text}

Respond directly to this new message from {user_name}:
"""

    try:
        # Show typing status for a realistic feel, but only if we are likely to reply
        # (If it's a direct reply to the bot, definitely show typing)
        if is_reply_to_bot or len(message.text.split()) > 3:
            await app.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

        # Call API
        response = await ai_client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": current_msg}
            ],
            max_tokens=60,
            temperature=0.85,
            presence_penalty=0.6, # Helps prevent repeating the same phrases
            frequency_penalty=0.6
        )

        ai_reply = response.choices[0].message.content.strip()

        # Update Memory
        history.append(current_msg)
        
        # Check if the AI decided to ignore the message
        if ai_reply.upper() == "IGNORE" or not ai_reply:
            return

        # Add bot's reply to memory
        history.append(f"You: {ai_reply}")

        # Send the message
        await message.reply_text(ai_reply)

    except Exception as e:
        logger.error(f"AI Chatbot Error in chat {message.chat.id}: {e}")
        # Do not expose raw errors to the user. Fail silently in group chats to prevent spam.
        pass
