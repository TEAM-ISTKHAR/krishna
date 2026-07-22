import asyncio
import random
import logging
import aiohttp
import httpx
from collections import defaultdict, deque
from typing import Optional, Dict, List

# 🔥 HTTPX PROXY CRASH PATCH (Heroku Fix)
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
        
        # 🚀 PREFETCH CACHE: Skip lag khatam karne ke liye
        self.prefetched_tracks: Dict[int, list] = defaultdict(list)

        # 🔥 MASSIVE CATEGORIZED ARTIST DATABASE
        self.artist_categories = {
            "bhojpuri": [
                "pawan singh", "khesari lal yadav", "shilpi raj", "antra singh", "pramod premi", 
                "ritesh pandey", "arvind akela kallu", "gunjan singh", "samar singh", "neha raj", 
                "manoj tiwari", "ravi kishan", "dinesh lal yadav", "nirahua", "kalpana", 
                "indu sonali", "priyanka singh", "ankush raja", "golu gold", "neelkamal singh", 
                "rakesh mishra", "akshara singh", "mohan rathore", "khushboo tiwari"
            ],
            "hindi": [
                "arijit singh", "shreya ghoshal", "atif aslam", "neha kakkar", "jubin nautiyal", 
                "darshan raval", "armaan malik", "sonu nigam", "badshah", "sunidhi chauhan", 
                "udit narayan", "kumar sanu", "alka yagnik", "sachet tandon", "parampara", 
                "b praak", "vishal mishra", "shilpa rao", "kk", "mohit chauhan", "ar rahman", 
                "pritam", "mithoon", "kishore kumar", "lata mangeshkar", "asha bhosle", 
                "mukesh", "mohammed rafi", "mika singh", "yo yo honey singh", "guru randhawa", 
                "tony kakkar", "neeti mohan", "monali thakur", "palak muchhal", "amit trivedi", 
                "rahat fateh ali khan", "shafqat amanat ali", "tulsi kumar", "amaal mallik", 
                "stebin ben", "javed ali", "kailash kher", "shankar mahadevan", "dhvani bhanushali"
            ],
            "punjabi": [
                "sidhu moose wala", "karan aujla", "diljit dosanjh", "ap dhillon", "amrit maan", 
                "shubh", "kaka", "hardy sandhu", "guru randhawa", "jass manak", "parmish verma", 
                "jaani", "ammy virk", "garry sandhu", "jassie gill", "babbu maan", "gurdas maan", 
                "sharry mann", "mankirt aulakh", "nimrat khaira", "jasmine sandlas", "sunanda sharma", 
                "bohemia", "imran khan", "jazzy b", "gippy grewal", "akhil", "prabh gill", "guri", 
                "tarsem jassar", "ranjit bawa"
            ],
            "haryanvi": [
                "sapna choudhary", "renuka panwar", "gulzaar chhaniwala", "sumit goswami", 
                "raju punjabi", "amit saini rohtakiya", "pranjal dahiya", "md kd", "masoom sharma", 
                "fazilpuria", "gajender phogat", "vikas kumar", "raj mawar", "surender romio", 
                "ruchika jangid", "anu kadyan", "diler kharkiya", "kd desi rock", "ajay hooda", 
                "anjali raghav"
            ],
            "south": [
                "anirudh", "ar rahman", "yuvan shankar raja", "sid sriram", "harris jayaraj", 
                "ilaiyaraaja", "spb", "s p balasubrahmanyam", "k s chithra", "sujatha", 
                "karthik", "vijay prakash", "benny dayal", "haricharan", "d imman", 
                "g v prakash", "santhosh narayanan", "devi sri prasad", "dsp", "thaman", 
                "anurag kulkarni", "mangli", "mm keeravani", "mani sharma", "sunitha", 
                "geetha madhuri", "rahul sipligunj", "ram miriyala"
            ],
            "english": [
                "taylor swift", "justin bieber", "ed sheeran", "ariana grande", "the weeknd", 
                "drake", "eminem", "billie eilish", "dua lipa", "post malone", "harry styles", 
                "selena gomez", "bruno mars", "maroon 5", "coldplay", "imagine dragons", 
                "rihanna", "beyonce", "adele", "lady gaga", "katy perry", "shawn mendes", 
                "charlie puth", "olivia rodrigo", "doja cat", "lil nas x", "kendrick lamar", 
                "j cole", "travis scott", "miley cyrus", "shakira", "david guetta", "calvin harris", 
                "alan walker", "marshmello"
            ]
        }

    async def _fetch_from_youtube_native(self, vidid: str) -> List[dict]:
        """Ultimate Vibe & Artist Matching Engine"""
        try:
            current_search = VideosSearch(f"https://youtube.com/watch?v={vidid}", limit=1)
            current_result = await current_search.next()
            if not current_result or not current_result.get("result"):
                return []
                
            track_info = current_result["result"][0]
            title = track_info.get("title", "").lower()
            channel_name = track_info.get("channel", {}).get("name", "").replace(" - Topic", "").replace("VEVO", "").strip().lower()
            
            clean_title = title.split("|")[0].split("(")[0].split("-")[0].split("[")[0].strip()

            detected_category = ""
            detected_artist = ""
            
            # 🔥 Detect EXACT Artist and Category
            for category, artists in self.artist_categories.items():
                for a in artists:
                    if a in title or a in channel_name:
                        detected_artist = a
                        detected_category = category
                        break
                if detected_artist:
                    break
                    
            # 🔥 Smart Query Builder
            if detected_artist and detected_category:
                search_query = f"{detected_artist} {detected_category} hit audio songs"
            elif channel_name:
                search_query = f"{channel_name} audio songs"
            else:
                short_title = " ".join(clean_title.split()[:2])
                search_query = f"{short_title} similar audio tracks"

            results = VideosSearch(search_query, limit=15)
            res = await results.next()
            
            tracks = []
            if res and res.get("result"):
                for track in res["result"]:
                    new_title = track.get("title", "").lower()
                    
                    # ANTI-REMIX
                    if len(clean_title) > 3 and clean_title in new_title:
                        continue
                    
                    # ANTI-TRASH
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
                async with session.get(url, timeout=3) as response:
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
                # 🔥 STRICT TIMER 1: Reject hours long tracks (1:26:00)
                if len(parts) > 2: 
                    return False 
                dur_sec = sum(int(x) * (60 ** i) for i, x in enumerate(reversed(parts)))
            else:
                dur_sec = int(duration)
                
            # 🔥 STRICT TIMER 2: MUST be between 1 minute and 7 minutes (420 seconds)
            if dur_sec < 60 or dur_sec > 420: 
                return False 
        except:
            return False
            
        return True

    async def get_valid_next_track(self, chat_id: int, current_vidid: str) -> Optional[dict]:
        for provider in self.providers:
            related_tracks = await self._fetch_from_api(provider, current_vidid)
            if not related_tracks: continue
            random.shuffle(related_tracks)
            for track in related_tracks:
                vidid = track.get("vidid") or track.get("id")
                if vidid:
                    track["vidid"] = vidid 
                    if vidid not in self.history[chat_id]:
                        if await self._validate_track(track):
                            return track
                            
        # LAST RESORT
        try:
            fallback_search = VideosSearch("latest hit audio songs 2024", limit=10)
            res = await fallback_search.next()
            if res and res.get("result"):
                for track in res["result"]:
                    vidid = track.get("id")
                    if vidid and vidid not in self.history[chat_id]:
                        track["vidid"] = vidid
                        if await self._validate_track(track):
                            return track
        except: pass
        return None

    async def _background_prefetch(self, chat_id: int, current_vidid: str):
        """🚀 BACKGROUND PREFETCH: Zero Lag Skip"""
        try:
            if len(self.prefetched_tracks[chat_id]) < 2:
                track = await self.get_valid_next_track(chat_id, current_vidid)
                if track:
                    self.prefetched_tracks[chat_id].append(track)
                    logger.info(f"✅ Background Prefetch Successful for {chat_id}")
        except Exception as e:
            logger.error(f"Prefetch error: {e}")

    async def process_autoplay(self, chat_id: int, current_vidid: str) -> bool:
        async with self.locks[chat_id]: 
            try:
                logger.info(f"🔄 Autoplay Processing {chat_id}")
                
                next_track = None
                
                # 🚀 ZERO-LAG SKIP FIX
                if self.prefetched_tracks[chat_id]:
                    next_track = self.prefetched_tracks[chat_id].pop(0)
                    logger.info("⚡ Using pre-fetched track for zero lag!")
                else:
                    next_track = await self.get_valid_next_track(chat_id, current_vidid)

                if not next_track:
                    return False

                vidid = next_track['vidid']
                self.history[chat_id].append(vidid)

                await self.stream_client._enqueue_autoplay_track(chat_id, next_track)
                
                # PREPARE NEXT SONG IMMEDIATELY
                asyncio.create_task(self._background_prefetch(chat_id, vidid))
                
                return True

            except Exception as e:
                logger.error(f"❌ Autoplay crash in {chat_id}: {e}")
                return False
