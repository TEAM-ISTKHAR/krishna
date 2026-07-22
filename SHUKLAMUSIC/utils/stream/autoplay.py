import asyncio
import random
import logging
import aiohttp
from collections import defaultdict, deque
from typing import Optional, Dict, List
from youtubesearchpython.__future__ import VideosSearch

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoplayManager")

class AdvancedAutoplay:
    def __init__(self, stream_client):
        self.stream_client = stream_client
        self.history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self.locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Added native YouTube as the ultimate fallback
        self.providers = ["shruti", "inflex", "youtube_native"]

    async def _fetch_from_youtube_native(self, vidid: str) -> List[dict]:
        """Ultimate fallback: Directly scrapes YouTube without any API Keys"""
        try:
            current_search = VideosSearch(f"https://youtube.com/watch?v={vidid}", limit=1)
            current_result = await current_search.next()
            if not current_result or not current_result.get("result"):
                return []
                
            title = current_result["result"][0]["title"]
            clean_title = title.split("|")[0].split("(")[0].strip()
            search_query = f"{clean_title} audio song"
            
            results = VideosSearch(search_query, limit=15)
            res = await results.next()
            
            tracks = []
            if res and res.get("result"):
                for track in res["result"]:
                    dur_str = track.get("duration")
                    if dur_str:
                        tracks.append({
                            "vidid": track.get("id"),
                            "title": track.get("title"),
                            "duration": dur_str
                        })
            return tracks
        except Exception as e:
            logger.warning(f"⚠️ Native YouTube Search Error: {e}")
            return []

    async def _fetch_from_api(self, provider: str, vidid: str) -> List[dict]:
        if provider == "youtube_native":
            return await self._fetch_from_youtube_native(vidid)
            
        # 🔥 YAHAN NAYA URL UPDATE KIYA HAI
        api_configs = {
            "shruti": f"https://shrutibots.site/related?id={vidid}&apikey=ShrutiBotsV1npoyhq8PrrjlVADSPU",
            "inflex": f"https://teaminflex.xyz/related?id={vidid}&apikey=INFLEX99600328D"
        }
        
        url = api_configs.get(provider)
        if not url: return []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, list): return data
                        elif isinstance(data, dict): return data.get("results") or data.get("data") or data.get("items") or []
                    else:
                        logger.warning(f"⚠️ {provider.capitalize()} API Down. Status: {response.status}")
        except Exception as e:
            logger.warning(f"⚠️ {provider.capitalize()} API Error: {e}")
            
        return []

    async def _validate_track(self, track: dict) -> bool:
        if not track: return False
        vidid = track.get("vidid") or track.get("id")
        if not vidid: return False
            
        try:
            duration = track.get("duration", 0)
            if isinstance(duration, str) and ":" in duration:
                parts = duration.split(":")
                dur_sec = sum(int(x) * (60 ** i) for i, x in enumerate(reversed(parts)))
            else:
                dur_sec = int(duration)
                
            if dur_sec < 60 or dur_sec > 3600: 
                return False 
        except:
            pass
            
        return True

    async def get_valid_next_track(self, chat_id: int, current_vidid: str) -> Optional[dict]:
        for provider in self.providers:
            related_tracks = await self._fetch_from_api(provider, current_vidid)
            
            if not related_tracks:
                continue

            random.shuffle(related_tracks)

            for track in related_tracks:
                vidid = track.get("vidid") or track.get("id")
                if vidid:
                    track["vidid"] = vidid 
                    if vidid not in self.history[chat_id]:
                        if await self._validate_track(track):
                            logger.info(f"✅ Track verified via {provider.capitalize()}")
                            return track
                            
        return None

    async def process_autoplay(self, chat_id: int, current_vidid: str) -> bool:
        async with self.locks[chat_id]: 
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"🔄 Autoplay Processing {chat_id} | Attempt {attempt + 1}")
                    
                    next_track = await self.get_valid_next_track(chat_id, current_vidid)
                    if not next_track:
                        raise ValueError("Sabhi APIs aur Fallbacks fail ho gaye.")

                    vidid = next_track['vidid']
                    self.history[chat_id].append(vidid)

                    await self.stream_client._enqueue_autoplay_track(chat_id, next_track)
                    return True

                except Exception as e:
                    logger.error(f"❌ Autoplay crash in {chat_id}: {e}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** (attempt + 1))
                    else:
                        logger.error(f"⚠️ Autoplay totally failed for {chat_id}.")
                        return False
