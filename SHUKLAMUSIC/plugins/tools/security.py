import asyncio
import re
from urllib.parse import unquote
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from SHUKLAMUSIC import app

# 👇 Yahan aapka Logger Group ID set hai
LOGGER_ID = -1003657932877

# 🚫 Banned NSFW Words List
BANNED_WORDS = [
    "porn", "pornhub", "xvideos", "xnxx", "brazzers", 
    "onlyfans", "xhamster", "hot bhabhi", "deskbabe", "redtube", "spankbang",
    "child porn", "pedophile", "pedo", "jailbait", "loli", "shota", "csam",
    "incest", "bestiality", "zoophilia", "snuff", "revenge porn", "nonconsensual"
]

def is_dangerous(text):
    if not text:
        return False, None
        
    decoded_text = unquote(str(text)).lower()
    
    # 1. Check for Adult/NSFW words
    for word in BANNED_WORDS:
        if re.search(r'\b' + re.escape(word) + r'\b', decoded_text):
            return True, "NSFW Adult Content"
            
    # 2. Check for Hack/Malicious IPs and Patterns
    bad_ips_patterns = [
        r"127\.0\.0\.1", r"169\.254", r"10\.0\.0", r"192\.168", r"0\.0\.0\.0", r"localhost",
        r"webhook\.site", r"requestbin\.com", r"ngrok\.io", r"localtunnel\.me",
        r"https?://.*@", # Blocks hidden credentials (http://hacker:pass@site.com)
    ]
    if any(re.search(p, decoded_text) for p in bad_ips_patterns):
        return True, "Malicious Link/IP"
        
    # 3. Check for Dangerous Extensions/Commands
    bad_extensions = [".sh", ".exe", ".bat", ".vbs", ".cmd", ".php"]
    if any(ext in decoded_text for ext in bad_extensions):
        return True, "Malicious File Extension"
        
    dangerous_chars = ["rm -rf", "wget ", "curl ", "chmod ", "bash -c", "eval(", "nc -e", "/bin/sh"]
    if any(char in decoded_text for char in dangerous_chars):
        return True, "Remote Code Execution Attempt"
        
    return False, None

async def delete_after_delay(msg, delay_seconds):
    await asyncio.sleep(delay_seconds)
    try:
        await msg.delete()
    except:
        pass

# group=-5 ensure karta hai ki yeh play.py se pehle chale
@app.on_message(filters.command(["play", "vplay", "cplay", "cvplay", "playforce", "vplayforce", "cplayforce", "cvplayforce"], prefixes=["/", "!", "%", ".", "@", "#"]) & filters.group, group=-5)
async def security_check(client, message: Message):
    text = message.text or message.caption
    
    # ✅ SABSE BADA FIX: Agar user kisi Telegram Audio/Video par reply karke /play likh raha hai, toh use aage jaane do!
    if message.reply_to_message:
        has_media = (
            message.reply_to_message.audio or 
            message.reply_to_message.voice or 
            message.reply_to_message.video or 
            message.reply_to_message.document
        )
        # Agar reply mein media hai aur command mein koi ganda text/URL nahi hai, toh SAFE hai.
        if has_media and len(message.command) == 1:
            return # Yahan se nikal jayega aur normal play.py apna kaam karega

    # 🚨 Check the text for malicious/NSFW content
    is_bad, breach_type = is_dangerous(text)
    
    if is_bad:
        video_url = "https://files.catbox.moe/5qgzw1.mp4"
        
        user_mention = message.from_user.mention if message.from_user else "Anonymous Admin"
        user_id = message.from_user.id if message.from_user else "Unknown"
        username = f"@{message.from_user.username}" if message.from_user and message.from_user.username else "None"
        
        chat_id = message.chat.id
        chat_title = message.chat.title or "Private Group"
        chat_link = f"https://t.me/{message.chat.username}" if message.chat.username else f"`{chat_id}`"
            
        log_text = (
            f"🚨 **sᴇᴄᴜʀɪᴛʏ ᴀʟᴇʀᴛ: {breach_type}** 🚨\n\n"
            f"👤 **User:** {user_mention}\n"
            f"🆔 **User ID:** `{user_id}`\n"
            f"📛 **Username:** {username}\n"
            f"👥 **Group Name:** {chat_title}\n"
            f"🔗 **Link/ID:** {chat_link}\n\n"
            f"⚠️ **Payload/Input:**\n`{text}`"
        )
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚫 Ban User", callback_data=f"sec_ban_user_{user_id}"),
                InlineKeyboardButton("🛑 Leave Chat", callback_data=f"sec_leave_chat_{chat_id}")
            ]
        ])
        
        # 1. Logger group mein report bhejo
        try:
            await app.send_message(LOGGER_ID, log_text, reply_markup=buttons)
        except Exception as e:
            print(f"Security Logger Error: {e}")

        # 2. Main group se us gande/malicious message ko delete karo
        try:
            await message.delete()
        except:
            pass
            
        # 3. User ko warning do
        sent_msg = await message.reply_video(
            video=video_url, 
            caption=f"⚠️ **{breach_type} detected. This action is blocked.**\n\n_Your attempt has been securely logged._"
        )
        
        # 4. IMPORTANT: Pyrogram ko yahin rok do taaki play.py yeh gaana na bajaye!
        message.stop_propagation()
        
        # 5. Background mein 10 min (600 sec) baad video delete kar do
        asyncio.create_task(delete_after_delay(sent_msg, 600))


# --- 🚨 ADMIN CALLBACK HANDLERS FOR BUTTONS ---

@app.on_callback_query(filters.regex(r"^sec_ban_user_") & filters.user(LOGGER_ID)) 
async def ban_malicious_user(client, query):
    user_id = query.data.split("_")[3]
    if user_id == "Unknown":
        return await query.answer("Cannot ban anonymous admin!", show_alert=True)
    try:
        from SHUKLAMUSIC.utils.database import add_banned_user
        await add_banned_user(int(user_id))
        await query.answer("User successfully banned from using the bot!", show_alert=True)
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        await query.answer(f"Failed to ban: {e}", show_alert=True)

@app.on_callback_query(filters.regex(r"^sec_leave_chat_") & filters.user(LOGGER_ID))
async def leave_malicious_chat(client, query):
    chat_id = query.data.split("_")[3]
    try:
        await app.leave_chat(int(chat_id))
        await query.answer("Bot successfully left the malicious chat!", show_alert=True)
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        await query.answer(f"Failed to leave chat: {e}", show_alert=True)
