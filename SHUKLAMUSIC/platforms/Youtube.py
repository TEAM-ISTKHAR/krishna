# ---------------------------------------------------------------
# 🔸 ShrutiMusic Api Youtube.py file.
# 🔹 Developed & Maintained by: Shiv
# 📅 Copyright © 2025 – All Rights Reserved
# ❤️ Made with dedication and love by Shiv
# ---------------------------------------------------------------

import asyncio
import os
import random
import re
from typing import Union
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch, Playlist
import aiohttp

API_URL = os.environ.get("API_URL", "https://teaminflex.xyz")
API_KEY = os.environ.get("API_KEY", "INFLEX99600328D") 
DOWNLOAD_DIR = "downloads"

def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))

# ── Conversion lock: prevents two coroutines converting the same file ──
import threading as _threading
_conv_locks: dict = {}
_conv_lock_guard = _threading.Lock()

def _get_conv_lock(path: str):
    with _conv_lock_guard:
        if path not in _conv_locks:
            _conv_locks[path] = asyncio.Lock()
        return _conv_locks[path]

def _wav_path(mp3: str) -> str:
    return mp3.replace(".mp3", ".wav")

def _tmp_wav_path(mp3: str) -> str:
    return mp3.replace(".mp3", ".wav.tmp")

async def _convert_to_wav(mp3_path: str) -> str:
    """
    Pre-convert MP3 → 48 kHz stereo PCM WAV so pytgcalls streams with
    zero decode overhead (only Opus encode needed during playback).
    Uses a .tmp file + atomic rename to prevent partial-file reads.
    """
    wav  = _wav_path(mp3_path)
    tmp  = _tmp_wav_path(mp3_path)

    if os.path.exists(wav) and os.path.getsize(wav) > 0:
        return wav

    lock = _get_conv_lock(mp3_path)
    async with lock:
        if os.path.exists(wav) and os.path.getsize(wav) > 0:
            return wav

        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass

        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y",
                "-threads", "0",          
                "-i", mp3_path,
                "-ar", "48000",           
                "-ac", "2",               
                "-acodec", "pcm_s16le",   
                "-map_metadata", "-1",    
                tmp,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

            if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                os.replace(tmp, wav)       
                return wav
        except Exception:
            pass
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass

    return mp3_path

def _cleanup_wav_cache(keep: int = 25) -> None:
    try:
        wavs = [
            os.path.join(DOWNLOAD_DIR, f)
            for f in os.listdir(DOWNLOAD_DIR)
            if f.endswith(".wav")
        ]
        if len(wavs) <= keep:
            return
        wavs.sort(key=lambda p: os.path.getatime(p))
        for old in wavs[: len(wavs) - keep]:
            try:
                os.remove(old)
                mp3 = old.replace(".wav", ".mp3")
                if os.path.exists(mp3):
                    os.remove(mp3)
            except Exception:
                pass
    except Exception:
        pass


async def download_song(link: str) -> str:
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if not video_id or len(video_id) < 3:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    mp3_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")
    wav_path = _wav_path(mp3_path)

    if os.path.exists(wav_path) and os.path.getsize(wav_path) > 0:
        return wav_path

    if not (os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0):
        downloaded = False
        for attempt in range(2):          
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{API_URL}/download",
                        params={"url": video_id, "type": "audio", "api_key": API_KEY},
                        timeout=aiohttp.ClientTimeout(total=300),
                    ) as resp:
                        if resp.status != 200:
                            break
                        tmp_dl = mp3_path + ".dl"
                        with open(tmp_dl, "wb") as f:
                            async for chunk in resp.content.iter_chunked(131072):
                                f.write(chunk)
                        if os.path.exists(tmp_dl) and os.path.getsize(tmp_dl) > 0:
                            os.replace(tmp_dl, mp3_path)
                            downloaded = True
                            break
            except Exception:
                if os.path.exists(mp3_path + ".dl"):
                    try:
                        os.remove(mp3_path + ".dl")
                    except Exception:
                        pass
                if attempt == 0:
                    await asyncio.sleep(2)   

        if not downloaded or not (os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0):
            return None

    result = await _convert_to_wav(mp3_path)
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _cleanup_wav_cache, 25)

    return result


async def download_video(link: str) -> str:
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if not video_id or len(video_id) < 3:
        return None

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_URL}/download",
                params={"url": video_id, "type": "video", "api_key": API_KEY},
                timeout=aiohttp.ClientTimeout(total=600)
            ) as resp:
                if resp.status != 200:
                    return None
                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072):
                        f.write(chunk)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return file_path
        return None
    except Exception:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        return None


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video download error: {e}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        try:
            plist = await Playlist.get(link)
        except Exception:
            return []
        videos = plist.get("videos") or []
        ids = []
        for data in videos[:limit]:
            if not data:
                continue
            vid = data.get("id")
            if not vid:
                continue
            ids.append(vid)
        return ids

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {
            "quiet": True,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android_embedded", "web_creator"],
                    "player_skip": ["webpage"],
                }
            },
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 11; Pixel 5) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/90.0.4430.91 Mobile Safari/537.36"
                ),
            },
        }
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append(
                            {
                                "format": format["format"],
                                "filesize": format.get("filesize"),
                                "format_id": format["format_id"],
                                "ext": format["ext"],
                                "format_note": format["format_note"],
                                "yturl": link,
                            }
                        )
                except Exception:
                    continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        try:
            if video:
                downloaded_file = await download_video(link)
            else:
                downloaded_file = await download_song(link)
            if downloaded_file:
                return downloaded_file, True
            return None, False
        except Exception:
            return None, False

    async def get_related(self, videoid: str, history: list = None, *args, **kwargs):
        """
        Ultra Smart Autoplay Engine: 
        Uses Language, Mood & Artist matching Dictionary with Anti-Trash & Anti-Duplicate filtering.
        """
        if history is None:
            history = []
            
        try:
            # 🛑 STRICT ANTI-TRASH FILTER
            blocked_words = [
                "news", "vlog", "interview", "podcast", "episode", "trailer", 
                "teaser", "movie", "review", "reaction", "unboxing", "investigates", 
                "documentary", "short", "scene"
            ]

            # --- 1. ULTRA SMART DICTIONARY MATCHER ---
            results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
            res = await results.next()
            
            if res and res.get("result"):
                track_info = res["result"][0]
                title = track_info.get("title", "")
                channel_name = track_info.get("channel", {}).get("name", "")
                title_lower = title.lower() + " " + channel_name.lower()
                
                keywords_map = {
                    "Hindi": [
                        "hindi", "bollywood", "arijit singh", "shreya ghoshal", "atif aslam", "neha kakkar", "jubin nautiyal", 
                        "darshan raval", "armaan malik", "sonu nigam", "badshah", "sunidhi chauhan", 
                        "udit narayan", "kumar sanu", "alka yagnik", "sachet tandon", "parampara", 
                        "b praak", "vishal mishra", "shilpa rao", "kk", "mohit chauhan", "ar rahman", 
                        "pritam", "mithoon", "kishore kumar", "lata mangeshkar", "asha bhosle", 
                        "mukesh", "mohammed rafi", "mika singh", "yo yo honey singh", "guru randhawa", 
                        "tony kakkar", "neeti mohan", "monali thakur", "palak muchhal", "amit trivedi", 
                        "rahat fateh ali khan", "shafqat amanat ali", "tulsi kumar", "amaal mallik", 
                        "rochak kohli", "stebin ben", "javed ali", "kailash kher", "shankar mahadevan",
                        "amit mishra", "dhvani bhanushali", "divya kumar", "nakash aziz", "t-series", "zee music"
                    ],
                    "Punjabi": [
                        "punjabi", "pollywood", "sidhu moose wala", "karan aujla", "diljit dosanjh", "ap dhillon", "amrit maan", 
                        "shubh", "kaka", "hardy sandhu", "guru randhawa", "jass manak", "parmish verma", 
                        "jaani", "ammy virk", "garry sandhu", "jassie gill", "babbu maan", "gurdas maan", 
                        "sharry mann", "mankirt aulakh", "nimrat khaira", "jasmine sandlas", "sunanda sharma", 
                        "miss pooja", "bohemia", "imran khan", "dr zeus", "jazzy b", "gippy grewal", 
                        "akhil", "prabh gill", "guri", "tarsem jassar", "ranjit bawa", "kavita seth", "speed records"
                    ],
                    "Bhojpuri": [
                        "bhojpuri", "pawan singh", "khesari lal yadav", "shilpi raj", "antra singh", "pramod premi", 
                        "ritesh pandey", "arvind akela kallu", "gunjan singh", "samar singh", "neha raj", 
                        "manoj tiwari", "ravi kishan", "dinesh lal yadav", "nirahua", "kalpana", 
                        "indu sonali", "priyanka singh", "ankush raja", "golu gold", "neelkamal singh", 
                        "rakesh mishra", "akshara singh", "mohan rathore", "khushboo tiwari"
                    ],
                    "Haryanvi": [
                        "haryanvi", "sapna choudhary", "renuka panwar", "gulzaar chhaniwala", "sumit goswami", 
                        "raju punjabi", "amit saini rohtakiya", "pranjal dahiya", "md kd", "masoom sharma", 
                        "fazilpuria", "gajender phogat", "vikas kumar", "raj mawar", "surender romio", 
                        "ruchika jangid", "anu kadyan", "diler kharkiya", "kd desi rock", "ajay hooda", 
                        "danjal", "anjali raghav"
                    ],
                    "Tamil": [
                        "tamil", "kollywood", "anirudh", "ar rahman", "yuvan shankar raja", "sid sriram", "harris jayaraj", 
                        "ilaiyaraaja", "spb", "s p balasubrahmanyam", "k s chithra", "sujatha", 
                        "karthik", "vijay prakash", "benny dayal", "haricharan", "d imman", 
                        "g v prakash", "santhosh narayanan", "vidyasagar", "deva", "pradeep kumar", 
                        "sean roldan", "chinmayi", "shweta mohan", "hariharan", "naresh iyer"
                    ],
                    "Telugu": [
                        "telugu", "tollywood", "devi sri prasad", "dsp", "thaman", "sid sriram", "anurag kulkarni", "mangli", 
                        "mm keeravani", "mani sharma", "s p balasubrahmanyam", "k s chithra", "sunitha", 
                        "geetha madhuri", "rahul sipligunj", "ram miriyala", "mickey j meyer", 
                        "gopi sundar", "s p b charan", "singer smita", "karthik", "hemanth", "inno genga"
                    ],
                    "English": [
                        "english", "hollywood", "pop", "taylor swift", "justin bieber", "ed sheeran", "ariana grande", "the weeknd", 
                        "drake", "eminem", "billie eilish", "dua lipa", "post malone", "harry styles", 
                        "selena gomez", "bruno mars", "maroon 5", "coldplay", "imagine dragons", 
                        "rihanna", "beyonce", "adele", "lady gaga", "katy perry", "shawn mendes", 
                        "charlie puth", "olivia rodrigo", "doja cat", "lil nas x", "kendrick lamar", 
                        "j cole", "travis scott", "miley cyrus", "shakira", "david guetta", "calvin harris"
                    ]
                }

                ignore_artist_kws = ["hindi", "punjabi", "bhojpuri", "haryanvi", "tamil", "telugu", "english", "bollywood", "pollywood", "tollywood", "kollywood", "hollywood", "pop", "t-series", "zee music", "speed records"]

                detected_lang = ""
                detected_artist = ""
                detected_mood = ""
                
                moods_list = ["sad", "love", "romantic", "lofi", "chill", "party", "mashup", "emotional", "heartbreak", "dance", "dj", "remix", "slowed", "reverb"]
                for mood in moods_list:
                    if mood in title_lower:
                        detected_mood = mood
                        break

                for lang, kws in keywords_map.items():
                    for kw in kws:
                        if kw in title_lower:
                            detected_lang = lang
                            if kw not in ignore_artist_kws:
                                detected_artist = kw.title()
                            break
                    if detected_lang:
                        break
                
                # Cleaning Title for Anti-Duplicate Check
                clean_title = re.sub(r'\(.*?\)|\[.*?\]|official|lyrical|video|audio|remix|hd|4k', '', title, flags=re.IGNORECASE).strip().lower()
                
                # Build Search Query: 🟢 STRICT MUSIC FORCE ("official audio song")
                search_parts = []
                if detected_artist: search_parts.append(detected_artist)
                if detected_mood: search_parts.append(detected_mood)
                if detected_lang: search_parts.append(detected_lang)
                
                if not search_parts:
                    search_query = f"{clean_title} official audio song"
                else:
                    search_query = f"{' '.join(search_parts)} hit official audio song"

                search_results = VideosSearch(search_query, limit=15)
                res_search = await search_results.next()
                
                if res_search and res_search.get("result"):
                    for track in res_search["result"]:
                        track_id = track.get("id")
                        
                        if track_id and track_id != videoid and track_id not in history:
                            track_title = track.get("title", "")
                            track_clean = re.sub(r'\(.*?\)|\[.*?\]|official|lyrical|video|audio|remix|hd|4k', '', track_title, flags=re.IGNORECASE).strip().lower()
                            
                            # 🛑 ANTI-TRASH CHECK: Filter News & Vlogs
                            is_trash = any(word in track_clean for word in blocked_words)
                            if is_trash:
                                continue
                            
                            # ⏱ DURATION FILTER: Ignore shorts (< 1.5 mins) & long documentaries/news (> 10 mins)
                            dur = track.get("duration", "0:00")
                            parts = dur.split(":")
                            duration_sec = sum(int(x) * (60 ** i) for i, x in enumerate(reversed(parts)))
                            
                            if duration_sec < 90 or duration_sec > 600:
                                continue

                            # ANTI-DUPLICATE: Must be a different song
                            if track_clean and track_clean != clean_title and clean_title not in track_clean:
                                return {
                                    "vidid": track_id,
                                    "title": track.get("title", "Unknown Title"),
                                    "duration": dur,
                                    "duration_sec": duration_sec
                                }
        except Exception:
            pass

        # --- 2. Regular YouTube Scrape Fallback (Strict Music Filter) ---
        try:
            url = f"https://www.youtube.com/watch?v={videoid}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        html = await response.text()
                        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
                        
                        for vid in video_ids:
                            if vid != videoid and vid not in history:
                                results = VideosSearch(f"https://www.youtube.com/watch?v={vid} official audio song", limit=1)
                                res = await results.next()
                                if res and res.get("result"):
                                    track = res["result"][0]
                                    track_title = track.get("title", "").lower()

                                    # 🛑 ANTI-TRASH CHECK
                                    is_trash = any(word in track_title for word in blocked_words)
                                    if is_trash:
                                        continue

                                    dur = track.get("duration", "0:00")
                                    parts = dur.split(":")
                                    duration_sec = sum(int(x) * 60 ** i for i, x in enumerate(reversed(parts)))
                                    
                                    # ⏱ DURATION FILTER
                                    if duration_sec < 90 or duration_sec > 600:
                                        continue

                                    return {
                                        "vidid": track["id"],
                                        "title": track.get("title", "Unknown Title"),
                                        "duration": dur,
                                        "duration_sec": duration_sec
                                    }
        except Exception:
            pass

YouTube = YouTubeAPI()
