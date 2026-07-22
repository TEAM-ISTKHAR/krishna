import asyncio
import random
import logging
import aiohttp
import httpx
from collections import defaultdict, deque
from typing import Optional, Dict, List

# 🔥 ULTRA-FIX: HTTPX PROXY CRASH PATCH
_orig_init = httpx.AsyncClient.__init__
def _patched_init(self, *args, **kwargs):
    kwargs.pop('proxies', None)
    _orig_init(self, *args, **kwargs)
httpx.AsyncClient.__init__ = _patched_init

from youtubesearchpython.__future__ import VideosSearch

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoplayManager")

class AdvancedAutoplay:
    def __init__(self, stream_client):
        self.stream_client = stream_client
        self.history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self.locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.providers = ["shruti", "inflex", "youtube_native"]

        # Vibe & Artist DB for Exact Spotify-Style Matching
        self.moods = ["sad", "love", "romantic", "lofi", "chill", "party", "mashup", "emotional", "heartbreak", "dance", "dj", "slowed", "reverb", "bhakti"]
        self.artists = [
            "arijit singh", "shreya ghoshal", "atif aslam", "neha kakkar", "jubin nautiyal",
            "darshan raval", "armaan malik", "sonu nigam", "badshah", "sunidhi chauhan",
            "udit narayan", "kumar sanu", "alka yagnik", "sachet tandon", "b praak",
            "vishal mishra", "kk", "mohit chauhan", "ar rahman", "pritam",
            "kishore kumar", "lata mangeshkar", "mika singh", "yo yo honey singh", "guru randhawa",
            "sidhu moose wala", "karan aujla", "diljit dosanjh", "ap dhillon", "hardy sandhu",
            "pawan singh", "khesari lal yadav", "shilpi raj", "sapna choudhary",
            "anirudh", "yuvan shankar raja", "sid sriram", "devi sri prasad",
            "taylor swift", "justin bieber", "ed sheeran", "the weeknd", "drake", "bts"
        ]

    async def _fetch_from_youtube_native(self, vidid: str) -> List[dict]:
        """Smart Vibe Engine: Maintains exact mood and artist without repeating."""
        try:
            current_search = VideosSearch(f"https://youtube.com/watch?v={vidid}", limit=1)
            current_result = await current_search.next()
            if not current_result or not current_result.get("result"):
                return []
                
            raw_title = current_result["result"][0].get("title", "")
            title = raw_title.lower()
            
            # 1. Detect Vibe & Artist
            detected_mood = random.choice(["hit", "popular", "best", "trending"])
            for m in self.moods:
                if m in title:
                    detected_mood = m
                    break
                    
            detected_artist = ""
            for a in self.artists:
                if a in title:
                    detected_artist = a
                    break

            clean_title = raw_title.split("|")[0].split("(")[0].split("-")[0].split("[")[0].strip().lower()

            # 2. Build Query (T-Series wale kachre ki jagah exact vibe search hogi)
            if detected_artist:
                search_query = f"{detected_artist} {detected_mood} audio songs"
            else:
                short_title = " ".join(clean_title.split()[:2])
                search_query = f"{short_title} {detected_mood} similar audio tracks"

            # 3. Fetch Tracks
            results = VideosSearch(search_query, limit=20)
            res = await results.next()
            
            tracks = []
            if res and res.get("result"):
                for track in res["result"]:
                    new_title = track.get("title", "").lower()
                    
                    # ANTI-REMIX: Agar purane gaane ka naam naye me hai (jaise Lofi, Slowed), toh skip karo
                    if len(clean_title) > 3 and clean_title in new_title:
                        continue
                        
                    # ANTI-TRASH: Faltu videos block karo
                    if any(w in new_title for w in ["news", "vlog", "interview", "podcast", "trailer", "teaser", "movie", "review", "reaction", "scene"]):
                        continue
                        
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
        except Exception:
            pass
            
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
                            
        # 🔥 THE ULTIMATE LAST RESORT: Agar sab fail ho jaye, toh randomly trending bja do par VC mat chhodo!
        try:
            fallback_search = VideosSearch("latest trending hit audio songs", limit=10)
            res = await fallback_search.next()
            if res and res.get("result"):
                for track in res["result"]:
                    vidid = track.get("id")
                    if vidid and vidid not in self.history[chat_id]:
                        track["vidid"] = vidid
                        if await self._validate_track(track):
                            return track
        except:
            pass
                            
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
