import asyncio
import random
import logging
import aiohttp
from collections import defaultdict, deque
from typing import Optional, Dict, List

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoplayManager")

class AdvancedAutoplay:
    def __init__(self, stream_client):
        self.stream_client = stream_client
        self.history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self.locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Sequence of providers to try (Shruti first, then Inflex as fallback)
        self.providers = ["shruti", "inflex"]

    async def _fetch_from_api(self, provider: str, vidid: str) -> List[dict]:
        """
        Dono APIs se smartly data nikalne ka logic.
        """
        api_configs = {
            "shruti": f"https://api01.shrutibots.site/related?id={vidid}&apikey=ShrutiBotsV1npoyhq8PrrjlVADSPU",
            "inflex": f"https://teaminflex.xyz/related?id={vidid}&apikey=INFLEX99600328D"
        }
        
        url = api_configs.get(provider)
        if not url: return []

        try:
            # 7 seconds timeout so bot doesn't hang if API is dead
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=7) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # 🔥 Robust JSON Parsing: API list return kare ya dict, dono handle ho jayega
                        if isinstance(data, list):
                            return data
                        elif isinstance(data, dict):
                            # Usually APIs wrap arrays in 'results', 'data', or 'items'
                            return data.get("results") or data.get("data") or data.get("items") or []
                    else:
                        logger.warning(f"⚠️ {provider.capitalize()} API Down. Status: {response.status}")
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ {provider.capitalize()} API Timeout (Lag too high).")
        except Exception as e:
            logger.warning(f"⚠️ {provider.capitalize()} API Error: {e}")
            
        return []

    async def _validate_track(self, track: dict) -> bool:
        """
        Gaane ko verify karta hai ki wo chalne laayak hai ya nahi.
        """
        if not track:
            return False
            
        vidid = track.get("vidid") or track.get("id")
        if not vidid:
            return False
            
        try:
            duration = track.get("duration", 0)
            if isinstance(duration, (int, float)) and duration > 3600:
                return False  # 1 ghante se upar ke podcasts/mix skip
        except:
            pass
            
        return True

    async def get_valid_next_track(self, chat_id: int, current_vidid: str) -> Optional[dict]:
        """
        Queue ke liye fresh gaana filter karta hai jo pehle na chala ho.
        """
        for provider in self.providers:
            related_tracks = await self._fetch_from_api(provider, current_vidid)
            
            if not related_tracks:
                continue

            random.shuffle(related_tracks)

            for track in related_tracks:
                vidid = track.get("vidid") or track.get("id")
                
                if vidid:
                    track["vidid"] = vidid  # Normalize key for queue
                    if vidid not in self.history[chat_id]:
                        if await self._validate_track(track):
                            logger.info(f"✅ Track verified via {provider.capitalize()}")
                            return track
                            
        return None

    async def process_autoplay(self, chat_id: int, current_vidid: str) -> bool:
        """
        Core Autoplay Execution Engine
        """
        async with self.locks[chat_id]: 
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"🔄 Autoplay Processing {chat_id} | Attempt {attempt + 1}")
                    
                    next_track = await self.get_valid_next_track(chat_id, current_vidid)
                    if not next_track:
                        raise ValueError("Dono APIs dead hain ya koi related gaana nahi mila.")

                    vidid = next_track['vidid']
                    
                    # Update History (Anti-repeat active)
                    self.history[chat_id].append(vidid)

                    # Trigger playback
                    await self.stream_client._enqueue_autoplay_track(chat_id, next_track)
                    
                    # Background buffering to kill delay
                    asyncio.create_task(self._prefetch_audio(chat_id, vidid))
                    
                    return True

                except Exception as e:
                    logger.error(f"❌ Autoplay crash in {chat_id}: {e}")
                    if attempt < max_retries - 1:
                        sleep_time = 2 ** (attempt + 1)
                        logger.info(f"⏳ Retrying in {sleep_time}s...")
                        await asyncio.sleep(sleep_time)
                    else:
                        logger.error(f"⚠️ Autoplay totally failed for {chat_id}.")
                        return False

    async def _prefetch_audio(self, chat_id: int, vidid: str):
        """
        Silent pre-loader task.
        """
        pass
