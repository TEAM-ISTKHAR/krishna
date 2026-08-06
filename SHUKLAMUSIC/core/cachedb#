# -----------------------------------------------
# 🔸 Cached Songs Database (External Mongo)
# -----------------------------------------------
from motor.motor_asyncio import AsyncIOMotorClient

# Aapka naya aur alag MongoDB URL cache ke liye
CACHE_MONGO_URI = "mongodb+srv://Sweettoxic:Sweettoxic@sweettoxic.mg57v4c.mongodb.net/?retryWrites=true&w=majority"

# Naya connection banayega
_mongo_client = AsyncIOMotorClient(CACHE_MONGO_URI)
cache_db = _mongo_client.CacheDatabase.cache_songs

async def get_cache(video_id: str):
    """
    Check karta hai ki kya gaana pehle se channel me dump hai.
    """
    document = await cache_db.find_one({"video_id": video_id})
    if document:
        return document.get("file_id")
    return None

async def save_cache(video_id: str, file_id: str):
    """
    Naye download hue gaane ka data MongoDB me save karta hai.
    """
    await cache_db.update_one(
        {"video_id": video_id}, 
        {"$set": {"file_id": file_id}},
        upsert=True
    )
