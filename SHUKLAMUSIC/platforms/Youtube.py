import asyncio
import os
import re
from typing import Union
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch, Playlist
import aiohttp
import logging

API_URL = os.environ.get("API_URL", "https://api01.shrutibots.site")
API_KEY = os.environ.get("API_KEY", "ShrutiBots2knm7tCsnIVesZt50Lwb") ## Get This API KEY FROM: @SHRUTIAPIBOT 
DOWNLOAD_DIR = "downloads"
LOGGER = logging.getLogger(__name__)

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

    # ✅ THE ULTIMATE AUTOPLAY FIX (Kabhi VC nahi chhodega)
    async def get_related(self, vidid: str, history: list) -> dict:
        try:
            import random
            from py_yt import VideosSearch

            search_query = "latest trending bollywood songs"
            
            try:
                curr_info = VideosSearch(f"https://www.youtube.com/watch?v={vidid}", limit=1)
                curr_res = (await curr_info.next()).get("result")
                if curr_res and len(curr_res) > 0:
                    title = curr_res[0].get("title", "")
                    channel_name = curr_res[0].get("channel", {}).get("name", "")
                    clean_title = re.sub(r'\[.*?\]|\(.*?\)','', title).strip()
                    if channel_name and "VEVO" not in channel_name.upper():
                        search_query = f"{channel_name} hit songs"
                    else:
                        search_query = f"{clean_title} official audio"
            except Exception:
                pass

            results = VideosSearch(search_query, limit=20)
            response = await results.next()
            
            if not response or not response.get("result"):
                results = VideosSearch("top 50 hit hindi songs", limit=15)
                response = await results.next()

            tracks = response.get("result", []) if response else []

            safe_tracks = [
                {"vidid": "1zLLM1YfGEo", "title": "Top Hindi Songs", "duration": "5:00", "duration_sec": 300},
                {"vidid": "Qf0BozxO9m0", "title": "Trending Hindi Hits", "duration": "4:30", "duration_sec": 270},
                {"vidid": "YfQ2y_pI-3s", "title": "Bollywood Lofi Mix", "duration": "4:45", "duration_sec": 285}
            ]

            if not tracks:
                return random.choice(safe_tracks)

            random.shuffle(tracks) 

            for track in tracks:
                track_id = track.get("id")
                if track_id and track_id not in history and track_id != vidid:
                    duration_min = track.get("duration")
                    if not duration_min or not isinstance(duration_min, str):
                        continue
                        
                    parts = duration_min.split(":")
                    if len(parts) > 2 or (len(parts) == 2 and int(parts[0]) > 12):
                        continue
                        
                    duration_sec = sum(int(x) * 60 ** i for i, x in enumerate(reversed(parts)))
                    
                    return {
                        "vidid": track_id,
                        "title": track.get("title", "Unknown Track"),
                        "duration": duration_min,
                        "duration_sec": duration_sec
                    }
            return random.choice(safe_tracks)
        except Exception:
            return {"vidid": "1zLLM1YfGEo", "title": "Fallback Track", "duration": "4:30", "duration_sec": 270}

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

YouTube = YouTubeAPI()
