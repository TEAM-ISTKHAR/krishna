import os
import aiohttp
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from SHUKLAMUSIC import app

# Async function for uploading file without blocking the bot
async def upload_file_async(file_path):
    url = "https://catbox.moe/user/api.php"
    try:
        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("reqtype", "fileupload")
                data.add_field("fileToUpload", f, filename=os.path.basename(file_path))
                
                async with session.post(url, data=data) as response:
                    if response.status == 200:
                        link = await response.text()
                        return True, link.strip()
                    else:
                        error_text = await response.text()
                        return False, f"ᴇʀʀᴏʀ {response.status}: {error_text}"
    except Exception as e:
        return False, f"Request failed: {str(e)}"


@app.on_message(filters.command(["tgm", "tgt", "telegraph", "tl"]))
async def get_link_group(client, message):
    if not message.reply_to_message:
        return await message.reply_text(
            "❍ ᴘʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇᴅɪᴀ (ᴘʜᴏᴛᴏ/ᴠɪᴅᴇᴏ/ᴅᴏᴄᴜᴍᴇɴᴛ) ᴛᴏ ᴜᴘʟᴏᴀᴅ."
        )

    media = message.reply_to_message
    file_size = 0
    if media.photo:
        file_size = media.photo.file_size
    elif media.video:
        file_size = media.video.file_size
    elif media.document:
        file_size = media.document.file_size
    else:
        return await message.reply_text("❍ ᴜɴsᴜᴘᴘᴏʀᴛᴇᴅ ᴍᴇᴅɪᴀ ᴛʏᴘᴇ.")

    # 200MB size limit check
    if file_size > 200 * 1024 * 1024:
        return await message.reply_text("❍ ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴍᴇᴅɪᴀ ғɪʟᴇ ᴜɴᴅᴇʀ 200MB.")

    text = await message.reply_text("❍ ᴅᴏᴡɴʟᴏᴀᴅɪɴɢ...")

    local_path = None
    try:
        # Progress callback removed to make download faster & avoid floodwaits
        local_path = await media.download()
        await text.edit_text("❍ ᴜᴘʟᴏᴀᴅɪɴɢ ᴛᴏ sᴇʀᴠᴇʀ...")

        success, upload_path = await upload_file_async(local_path)

        if success:
            await text.edit_text(
                f"❍ | [ᴛᴀᴘ ᴛʜᴇ ʟɪɴᴋ]({upload_path})",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "ᴛᴀᴘ ʜᴇʀᴇ ᴛᴏ sᴇᴇ",
                                url=upload_path,
                            )
                        ]
                    ]
                ),
            )
        else:
            await text.edit_text(
                f"❍ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ ᴡʜɪʟᴇ ᴜᴘʟᴏᴀᴅɪɴɢ:\n`{upload_path}`"
            )

    except Exception as e:
        await text.edit_text(f"❍ ғɪʟᴇ ᴜᴘʟᴏᴀᴅ ғᴀɪʟᴇᴅ\n\n❍ <i>ʀᴇᴀsᴏɴ: {e}</i>")
    
    finally:
        # Hamesha file delete karein, chahe error aaye ya successful ho
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
