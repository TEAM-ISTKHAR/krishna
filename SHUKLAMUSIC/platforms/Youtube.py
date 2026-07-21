import asyncio
import os
import re
from typing import Dict, List, Union

import yt_dlp
from youtubesearchpython.__future__ import Video, VideosSearch

from SHUKLAMUSIC.utils.formatters import time_to_seconds


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^\"&?\/\s]{11})"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x00?\?v=([a-zA-Z0-9_-]{11})")
        
        # Fast Audio Download Options (Bypassing external APIs)
        self.audio_opts = {
            "format": "bestaudio/best",
            "extractaudio": True,
            "audioformat": "mp3",
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "restrictfilenames": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "quiet": True,
            "no_warnings": True,
            "default_search": "auto",
            "source_address": "0.0.0.0",
        }
        
        # Fast Video Download Options
        self.video_opts = {
            "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "restrictfilenames": True,
            "noplaylist": True,
            "nocheckcertificate": True,
            "ignoreerrors": False,
            "logtostderr": False,
            "quiet": True,
            "no_warnings": True,
            "default_search": "auto",
            "source_address": "0.0.0.0",
        }

    # Extract Video ID
    async def extract_vidid(self, url: str) -> str:
        match = re.search(self.regex, url)
        if match:
            return match.group(1)
        return None

    # Base Info Fetcher
    async def video(self, link: str, videoid: Union[bool, str] = False) -> tuple:
        if videoid:
            link = self.base + link
        try:
            results = VideosSearch(link, limit=1)
            res = await results.next()
            if res and res.get("result"):
                track = res["result"][0]
                return 1, track.get("link")
            return 0, None
        except Exception:
            return 0, None

    # Search Query
    async def search(self, query: str, limit: int = 5) -> List[Dict]:
        try:
            results = VideosSearch(query, limit=limit)
            res = await results.next()
            if res and res.get("result"):
                return res["result"]
            return []
        except Exception:
            return []
            
    # Track Info Fetcher
    async def track(self, link: str, videoid: Union[bool, str] = False) -> tuple:
        if videoid:
            link = self.base + link
        try:
            video_info = await Video.get(link)
            if video_info:
                vidid = video_info.get("id")
                title = video_info.get("title")
                duration_min = video_info.get("duration", "0:00")
                parts = duration_min.split(":")
                duration_sec = sum(int(x) * 60 ** i for i, x in enumerate(reversed(parts)))
                return track_details(vidid, title, duration_min, duration_sec)
        except Exception:
            pass

        # Fallback to search
        try:
            results = VideosSearch(link, limit=1)
            res = await results.next()
            if res and res.get("result"):
                track = res["result"][0]
                vidid = track.get("id")
                title = track.get("title")
                duration_min = track.get("duration", "0:00")
                parts = duration_min.split(":")
                duration_sec = sum(int(x) * 60 ** i for i, x in enumerate(reversed(parts)))
                return track_details(vidid, title, duration_min, duration_sec)
        except Exception:
            return 0, None, None, None

        return 0, None, None, None
    # Thumbnail Fetcher
    async def thumbnail(self, link: str, videoid: Union[bool, str] = False) -> str:
        if videoid:
            return f"https://img.youtube.com/vi/{link}/maxresdefault.jpg"
        vidid = await self.extract_vidid(link)
        if vidid:
            return f"https://img.youtube.com/vi/{vidid}/maxresdefault.jpg"
        return None

    # Autoplay / Related Videos Fetcher (ALONE-X Style Smart Fetching)
    async def get_related(self, videoid: str, history: list = []) -> Dict:
        try:
            video_info = await Video.get(videoid)
            if video_info and "channel" in video_info:
                channel_name = video_info["channel"].get("name", "")
                search_query = f"{channel_name} songs"
                results = VideosSearch(search_query, limit=10)
                res = await results.next()
                if res and res.get("result"):
                    for track in res["result"]:
                        track_id = track.get("id")
                        if track_id != videoid and track_id not in history and track.get("duration"):
                            dur = track.get("duration", "0:00")
                            parts = dur.split(":")
                            duration_sec = sum(int(x) * 60 ** i for i, x in enumerate(reversed(parts)))
                            return {
                                "vidid": track_id,
                                "title": track.get("title", "Unknown Title"),
                                "duration": dur,
                                "duration_sec": duration_sec
                            }
        except Exception:
            pass

        # Fallback Strict Search
        try:
            search_query = f"https://www.youtube.com/watch?v={videoid}"
            results = VideosSearch(search_query, limit=5)
            res = await results.next()
            if res and res.get("result"):
                for track in res["result"]:
                    track_id = track.get("id")
                    if track_id != videoid and track_id not in history and track.get("duration"):
                        dur = track.get("duration", "0:00")
                        parts = dur.split(":")
                        duration_sec = sum(int(x) * 60 ** i for i, x in enumerate(reversed(parts)))
                        return {
                            "vidid": track_id,
                            "title": track.get("title", "Unknown Title"),
                            "duration": dur,
                            "duration_sec": duration_sec
                        }
        except Exception:
            return None
        return None

    # Fast Download Engine (No Shruti API, pure yt-dlp)
    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = False,
        videoid: Union[bool, str] = False,
    ) -> tuple:
        if videoid:
            link = self.base + link
        
        loop = asyncio.get_running_loop()
        
        def _download():
            opts = self.video_opts if video else self.audio_opts
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(link, download=False)
                    # Get correct extension
                    ext = info.get("ext", "mp4" if video else "mp3")
                    filepath = os.path.join("downloads", f"{info['id']}.{ext}")
                    
                    if not os.path.exists(filepath):
                        ydl.download([link])
                    return filepath, 1
            except Exception as e:
                return str(e), 0

        try:
            filepath, status = await loop.run_in_executor(None, _download)
            if status == 1:
                return filepath, 1
            else:
                raise Exception(filepath)
        except Exception as e:
            raise Exception(f"Download Failed: {e}")

def track_details(vidid, title, duration_min, duration_sec):
    return 1, vidid, title, duration_min, duration_sec
