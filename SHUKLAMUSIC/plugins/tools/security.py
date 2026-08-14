import asyncio
import re
from urllib.parse import unquote
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from SHUKLAMUSIC import app

LOGGER_ID = -1003657932877

def is_malicious_play(text):
    if not text:
        return False
        
    decoded_text = unquote(text)
    
    play_commands = ("/play", "/vplay", "/cplay", ".play", "!play", "play", "vplay")
    
    if not any(decoded_text.lower().startswith(cmd) for cmd in play_commands):
        return False  
        
    patterns = [
        r"webhook\.site",
        r"requestbin\.com",
        r"ngrok\.io",
        r"localtunnel\.me",
        r"localhost"
    ]
    
    return any(re.search(p, decoded_text, re.IGNORECASE) for p in patterns)

async def delete_after_delay(msg, delay_seconds):
    await asyncio.sleep(delay_seconds)
    try:
        await msg.delete()
    except:
        pass

@app.on_message(filters.text | filters.caption, group=-5)
async def handle_security(client, message):
    text = message.text or message.caption
    
    if text and is_malicious_play(text):
        video_url = "https://files.catbox.moe/5qgzw1.mp4"
        
        if message.from_user:
            user_id = message.from_user.id
            user_mention = message.from_user.mention
            username = f"@{message.from_user.username}" if message.from_user.username else "No Username"
        else:
            user_id = "Unknown (Anonymous)"
            user_mention = "Anonymous Admin"
            username = "None"

        chat_id = message.chat.id
        chat_title = message.chat.title if message.chat.title else "Private/Unknown"
        
        if message.chat.username:
            chat_link = f"https://t.me/{message.chat.username}"
        else:
            chat_link = f"`{chat_id}` (Private Group)"
            
        log_text = (
            f"🚨 **Malicious Play Attempt Detected** 🚨\n\n"
            f"👤 **User:** {user_mention}\n"
            f"🆔 **User ID:** `{user_id}`\n"
            f"📛 **Username:** {username}\n"
            f"👥 **Group Name:** {chat_title}\n"
            f"🔗 **Group Link/ID:** {chat_link}\n"
            f"💬 **Message Sent:**\n`{text}`"
        )
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚫 Ban User", callback_data=f"sec_ban_user_{user_id}"),
                InlineKeyboardButton("🛑 Leave Chat", callback_data=f"sec_leave_chat_{chat_id}")
            ]
        ])
        
        try:
            await app.send_message(LOGGER_ID, log_text, reply_markup=buttons)
        except Exception as e:
            print(f"Logger Error: {e}")

        try:
            await message.delete()
        except:
            pass
            
        sent_msg = await message.reply_video(
            video=video_url, 
            caption="⚠️ **Malicious link detected. This action is not allowed. Your attempt has been logged.**"
        )
        
        message.stop_propagation()
        
        asyncio.create_task(delete_after_delay(sent_msg, 3600))


@app.on_callback_query(filters.regex(r"^sec_ban_user_") & filters.user(LOGGER_ID)) 
async def ban_malicious_user(client, query):
    user_id = query.data.split("_")[3]
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
