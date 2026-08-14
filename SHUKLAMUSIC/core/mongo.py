from motor.motor_asyncio import AsyncIOMotorClient as _mongo_client_
from pymongo import MongoClient
from pyrogram import Client

import config
from ..logging import LOGGER

# Backup ke liye temp DB. Agar config me main DB nahi hai, tab ye kaam aayega.
TEMP_MONGODB = ""

if config.MONGO_DB_URI is None:
    LOGGER(__name__).warning("No MONGO DB URL found. Please add it in your config vars!")
    temp_client = Client(
        "MusicBot",
        bot_token=config.BOT_TOKEN,
        api_id=config.API_ID,
        api_hash=config.API_HASH,
    )
    temp_client.start()
    info = temp_client.get_me()
    username = info.username
    temp_client.stop()
    
    _mongo_async_ = _mongo_client_(TEMP_MONGODB)
    _mongo_sync_ = MongoClient(TEMP_MONGODB)
    mongodb = _mongo_async_[username]
    pymongodb = _mongo_sync_[username]
else:
    _mongo_async_ = _mongo_client_(config.MONGO_DB_URI)
    _mongo_sync_ = MongoClient(config.MONGO_DB_URI)
    
    # Aapke database ka naam yahan 'KavyaMusic' save hoga (Pehle Anon tha)
    mongodb = _mongo_async_.KavyaMusic
    pymongodb = _mongo_sync_.KavyaMusic
    
    LOGGER(__name__).info("✅ Connected to your Mongo Database Successfully.")
