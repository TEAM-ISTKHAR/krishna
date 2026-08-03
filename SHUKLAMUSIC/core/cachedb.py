from SHUKLAMUSIC.core.mongo import mongodb

# Naya collection banayega
cache_db = mongodb.cache_songs

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
    document = await cache_db.find_one({"video_id": video_id})
    if document:
        return await cache_db.update_one(
            {"video_id": video_id}, 
            {"$set": {"file_id": file_id}}
        )
    else:
        return await cache_db.insert_one(
            {"video_id": video_id, "file_id": file_id}
        )
