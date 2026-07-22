# Copyright (c) 2026 THE SHIV
# Licensed under the MIT License.
# This file is part of MahiMusic
# DEVELOPER - THE SHIV

import asyncio
import os
import random
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import ConnectionNotFound, TelegramServerError
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait 
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession
from youtubesearchpython.__future__ import Video, VideosSearch

import config
from SHUKLAMUSIC import LOGGER, YouTube, app
from SHUKLAMUSIC.misc import db
from SHUKLAMUSIC.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_lang,
    get_loop,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
    get_autoplay,
)
from SHUKLAMUSIC.utils.exceptions import AssistantErr
from SHUKLAMUSIC.utils.formatters import check_duration, seconds_to_min, speed_converter
from SHUKLAMUSIC.utils.inline.play import stream_markup
from SHUKLAMUSIC.utils.stream.autoclear import auto_clean
from SHUKLAMUSIC.utils.thumbnails import get_thumb as gen_thumb
from strings import get_string

autoend = {}
counter = {}

def get_random_img(img_list):
    if img_list:
        if isinstance(img_list, list):
            return random.choice(img_list)
        return img_list
    return "https://telegra.ph/file/2e3d368e77c449c287430.jpg" 

async def _delete_msg(msg, delay: int = 6):
    try:
        await asyncio.sleep(delay)
        await msg.delete()
    except Exception:
        pass

async def _clear_(chat_id: int):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)

class Call(PyTgCalls):
    def __init__(self):
        PyTgCallsSession.notice_displayed = True

        # --- Autoplay Variables ---
        self.history: dict[int, list[str]] = defaultdict(list)
        self.pending_autoplay = {}
        self.autoplay_prefetching = set()
        self.autoplay_failures = defaultdict(int)
        self.active_clients = {} 
        # --------------------------

        self.userbot1 = Client(
            name="SHUKLAAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(self.userbot1, cache_duration=100)

        self.userbot2 = Client(
            name="SHUKLAAss2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(self.userbot2, cache_duration=100)

        self.userbot3 = Client(
            name="SHUKLAAss3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(self.userbot3, cache_duration=100)

        self.userbot4 = Client(
            name="SHUKLAAss4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(self.userbot4, cache_duration=100)

        self.userbot5 = Client(
            name="SHUKLAAss5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(self.userbot5, cache_duration=100)

    def clear_autoplay(self, chat_id: int):
        self.autoplay_failures[chat_id] = 0
        self.pending_autoplay.pop(chat_id, None)
        self.autoplay_prefetching.discard(chat_id)
        self.history.pop(chat_id, None)

    def _build_stream(self, source: str, video: bool, ffmpeg: str | None = None) -> types.MediaStream:
        base_flags = "-threads 0"
        combined = f"{base_flags} {ffmpeg}" if ffmpeg else base_flags
        return types.MediaStream(
            media_path=source,
            audio_parameters=types.AudioQuality.MEDIUM,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(types.MediaStream.Flags.AUTO_DETECT if video else types.MediaStream.Flags.IGNORE),
            ffmpeg_parameters=combined,
        )

    async def _play_on_assistant(self, client: PyTgCalls, chat_id: int, stream: types.MediaStream):
        try:
            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=False),
            )
        except exceptions.NoActiveGroupCall: raise
        except exceptions.NoAudioSourceFound: raise
        except (ConnectionNotFound, TelegramServerError): raise
        except Exception: raise

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            self.clear_autoplay(chat_id)
            await _clear_(chat_id)
            await assistant.leave_call(chat_id, close=False)
        except Exception:
            pass

    async def stop_stream_force(self, chat_id: int):
        for string, client in [(config.STRING1, self.one), (config.STRING2, self.two), (config.STRING3, self.three), (config.STRING4, self.four), (config.STRING5, self.five)]:
            if not string: continue
            try: await client.leave_call(chat_id, close=False)
            except: pass
        try:
            self.clear_autoplay(chat_id)
            await _clear_(chat_id)
        except: pass

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                vs = {"0.5": 2.0, "0.75": 1.35, "1.5": 0.68, "2.0": 0.5}.get(str(speed), 1.0)
                proc = await asyncio.create_subprocess_shell(
                    cmd=(f"ffmpeg -i {file_path} -filter:v setpts={vs}*PTS -filter:a atempo={speed} {out}"),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path
        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        dur = int(dur)
        # Fixed KeyError: 'played' by using .get()
        played_time = playing[0].get("played", 0)
        played, con_seconds = speed_converter(played_time, speed)
        duration = seconds_to_min(dur)
        xx = f"-ss {played} -to {duration}"
        video_mode = playing[0]["streamtype"] == "video"
        stream = self._build_stream(out, video=video_mode, ffmpeg=xx)
        if str(db[chat_id][0]["file"]) == str(file_path):
            await self._play_on_assistant(assistant, chat_id, stream)
        else:
            raise AssistantErr("Umm")
        if str(db[chat_id][0]["file"]) == str(file_path):
            exis = (playing[0]).get("old_dur")
            if not exis:
                db[chat_id][0]["old_dur"] = db[chat_id][0]["dur"]
                db[chat_id][0]["old_second"] = db[chat_id][0]["seconds"]
            db[chat_id][0]["played"] = con_seconds
            db[chat_id][0]["dur"] = duration
            db[chat_id][0]["seconds"] = dur
            db[chat_id][0]["speed_path"] = out
            db[chat_id][0]["speed"] = speed

    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None):
        assistant = await group_assistant(self, chat_id)
        stream = self._build_stream(link, video=bool(video))
        await self._play_on_assistant(assistant, chat_id, stream)

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        ffmpeg = f"-ss {to_seek} -to {duration}"
        video_mode = mode == "video"
        stream = self._build_stream(file_path, video=video_mode, ffmpeg=ffmpeg)
        await self._play_on_assistant(assistant, chat_id, stream)

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOG_GROUP_ID)
        stream = self._build_stream(link, video=True)
        await self._play_on_assistant(assistant, config.LOG_GROUP_ID, stream)
        await asyncio.sleep(0.2)
        try: await assistant.leave_call(config.LOG_GROUP_ID, close=False)
        except: pass

    async def join_call(self, chat_id: int, original_chat_id: int, link, video: Union[bool, str] = None, image: Union[bool, str] = None):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)
        stream = self._build_stream(link, video=bool(video))
        try:
            await self._play_on_assistant(assistant, chat_id, stream)
        except exceptions.NoActiveGroupCall: raise AssistantErr(_["call_8"])
        except exceptions.NoAudioSourceFound: raise AssistantErr(_["call_10"])
        except (ConnectionNotFound, TelegramServerError): raise AssistantErr(_["call_10"])
        except Exception: raise AssistantErr(_["call_10"])
        
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video: await add_active_video_chat(chat_id)
        
        if await is_autoend():
            counter[chat_id] = {}
            try:
                users = len(await assistant.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except: pass

    async def change_stream(self, client: PyTgCalls, chat_id: int):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        
        try:
            if loop == 0:
                if check: popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            
            if popped: await auto_clean(popped)
            
            # --- 🟢 SPOTIFY-STYLE AUTOPLAY EXECUTION ---
            if not check:
                try:
                    auto_on = await get_autoplay(chat_id)
                except Exception:
                    auto_on = False

                if auto_on and popped:
                    vidid = popped.get("vidid")
                    if vidid and vidid not in ["telegram", "soundcloud"]:
                        LOGGER(__name__).info(f"🔄 Spotify-Style Autoplay triggered for {chat_id}")
                        self.history[chat_id].append(vidid)
                        del self.history[chat_id][:-20] 

                        raw_title = popped.get("title", "Unknown Title")
                        title_lower = str(raw_title).lower()
                        
                        try:
                            video_info = await Video.get(vidid)
                            if video_info:
                                channel_name = video_info.get("channel", {}).get("name", "")
                                title_lower += " " + channel_name.lower()
                        except: pass

                        keywords_map = {
                            "Hindi": [
                                "arijit singh", "shreya ghoshal", "atif aslam", "neha kakkar", "jubin nautiyal", 
                                "darshan raval", "armaan malik", "sonu nigam", "badshah", "sunidhi chauhan", 
                                "udit narayan", "kumar sanu", "alka yagnik", "sachet tandon", "parampara", 
                                "b praak", "vishal mishra", "shilpa rao", "kk", "mohit chauhan", "ar rahman", 
                                "pritam", "mithoon", "kishore kumar", "lata mangeshkar", "asha bhosle", 
                                "mukesh", "mohammed rafi", "mika singh", "yo yo honey singh", "guru randhawa", 
                                "tony kakkar", "neeti mohan", "monali thakur", "palak muchhal", "amit trivedi", 
                                "rahat fateh ali khan", "shafqat amanat ali", "tulsi kumar", "amaal mallik", 
                                "rochak kohli", "stebin ben", "javed ali", "kailash kher", "shankar mahadevan",
                                "amit mishra", "dhvani bhanushali", "divya kumar", "nakash aziz"
                            ],
                            "Punjabi": [
                                "sidhu moose wala", "karan aujla", "diljit dosanjh", "ap dhillon", "amrit maan", 
                                "shubh", "kaka", "hardy sandhu", "guru randhawa", "jass manak", "parmish verma", 
                                "jaani", "ammy virk", "garry sandhu", "jassie gill", "babbu maan", "gurdas maan", 
                                "sharry mann", "mankirt aulakh", "nimrat khaira", "jasmine sandlas", "sunanda sharma", 
                                "miss pooja", "bohemia", "imran khan", "dr zeus", "jazzy b", "gippy grewal", 
                                "akhil", "prabh gill", "guri", "tarsem jassar", "ranjit bawa", "kavita seth"
                            ],
                            "Bhojpuri": [
                                "pawan singh", "khesari lal yadav", "shilpi raj", "antra singh", "pramod premi", 
                                "ritesh pandey", "arvind akela kallu", "gunjan singh", "samar singh", "neha raj", 
                                "manoj tiwari", "ravi kishan", "dinesh lal yadav", "nirahua", "kalpana", 
                                "indu sonali", "priyanka singh", "ankush raja", "golu gold", "neelkamal singh", 
                                "rakesh mishra", "akshara singh", "mohan rathore", "khushboo tiwari"
                            ],
                            "Haryanvi": [
                                "sapna choudhary", "renuka panwar", "gulzaar chhaniwala", "sumit goswami", 
                                "raju punjabi", "amit saini rohtakiya", "pranjal dahiya", "md kd", "masoom sharma", 
                                "fazilpuria", "gajender phogat", "vikas kumar", "raj mawar", "surender romio", 
                                "ruchika jangid", "anu kadyan", "diler kharkiya", "kd desi rock", "ajay hooda", 
                                "danjal", "anjali raghav"
                            ],
                            "Tamil": [
                                "anirudh", "ar rahman", "yuvan shankar raja", "sid sriram", "harris jayaraj", 
                                "ilaiyaraaja", "spb", "s p balasubrahmanyam", "k s chithra", "sujatha", 
                                "karthik", "vijay prakash", "benny dayal", "haricharan", "d imman", 
                                "g v prakash", "santhosh narayanan", "vidyasagar", "deva", "pradeep kumar", 
                                "sean roldan", "chinmayi", "shweta mohan", "hariharan", "naresh iyer"
                            ],
                            "Telugu": [
                                "devi sri prasad", "dsp", "thaman", "sid sriram", "anurag kulkarni", "mangli", 
                                "mm keeravani", "mani sharma", "s p balasubrahmanyam", "k s chithra", "sunitha", 
                                "geetha madhuri", "rahul sipligunj", "ram miriyala", "mickey j meyer", 
                                "gopi sundar", "s p b charan", "singer smita", "karthik", "hemanth", "inno genga"
                            ],
                            "English": [
                                "taylor swift", "justin bieber", "ed sheeran", "ariana grande", "the weeknd", 
                                "drake", "eminem", "billie eilish", "dua lipa", "post malone", "harry styles", 
                                "selena gomez", "bruno mars", "maroon 5", "coldplay", "imagine dragons", 
                                "rihanna", "beyonce", "adele", "lady gaga", "katy perry", "shawn mendes", 
                                "charlie puth", "olivia rodrigo", "doja cat", "lil nas x", "kendrick lamar", 
                                "j cole", "travis scott", "miley cyrus", "shakira", "david guetta", "calvin harris"
                            ]
                        }

                        ignore_artist_kws = ["hindi", "punjabi", "bhojpuri", "haryanvi", "tamil", "telugu", "english"]
                        blocked_words = ["news", "vlog", "interview", "podcast", "episode", "trailer", "teaser", "movie", "review", "reaction", "unboxing", "investigates", "documentary", "short", "scene"]

                        detected_lang = ""
                        detected_artist = ""
                        detected_mood = ""
                        
                        moods_list = ["sad", "love", "romantic", "lofi", "chill", "party", "mashup", "emotional", "heartbreak", "dance", "dj"]
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

                        # Spotify Query Logic: Same Artist (70%) or Same Language New Artist (30%)
                        query_parts = []
                        if detected_lang:
                            available_singers = [s for s in keywords_map[detected_lang] if s not in ignore_artist_kws]
                            if detected_artist and random.randint(1, 10) <= 7:
                                query_parts.append(detected_artist)
                            elif available_singers:
                                new_singer = random.choice(available_singers).title()
                                query_parts.append(new_singer)
                                detected_artist = new_singer  
                        elif detected_artist:
                            query_parts.append(detected_artist)
                            
                        if query_parts:
                            if detected_mood: query_parts.append(detected_mood)
                            random_modifiers = ["audio track", "lyrical", "best of", "hits", "new", "live", "unplugged"]
                            query_parts.append(random.choice(random_modifiers))
                            search_query = " ".join(query_parts)
                        else:
                            clean_title = re.sub(r'[\[\(].*?[\]\)]', '', str(raw_title))
                            clean_title = clean_title.split("|")[0].split("-")[0].split(",")[0].strip()
                            fallback_modifiers = ["similar artists", "playlist", "radio mix", "hits"]
                            search_query = f"{clean_title} {random.choice(fallback_modifiers)}"
                            detected_artist = "Smart Fallback"

                        # 🟢 EXECUTE SMART SEARCH
                        recommendation = None
                        try:
                            results = VideosSearch(search_query, limit=15)
                            res = await results.next()
                            
                            clean_original_title = re.sub(r'\(.*?\)|\[.*?\]|official|lyrical|video|audio|remix|hd|4k', '', str(raw_title), flags=re.IGNORECASE).strip().lower()
                            
                            if res and res.get("result"):
                                for track in res["result"]:
                                    track_id = track.get("id")
                                    if track_id and track_id != vidid and track_id not in self.history[chat_id]:
                                        track_title = track.get("title", "")
                                        track_clean = re.sub(r'\(.*?\)|\[.*?\]|official|lyrical|video|audio|remix|hd|4k', '', track_title, flags=re.IGNORECASE).strip().lower()
                                        
                                        # ANTI-TRASH CHECK
                                        if any(word in track_clean.lower() for word in blocked_words): continue
                                        
                                        # ANTI-DUPLICATE CHECK
                                        if track_clean and track_clean != clean_original_title and clean_original_title not in track_clean:
                                            dur = track.get("duration", "0:00")
                                            parts = dur.split(":")
                                            duration_sec = sum(int(x) * (60 ** i) for i, x in enumerate(reversed(parts)))
                                            
                                            # DURATION FILTER (1.5 Min to 10 Min)
                                            if duration_sec < 90 or duration_sec > 600: continue
                                            
                                            recommendation = {
                                                "vidid": track_id,
                                                "title": track.get("title", "Unknown Title"),
                                                "duration_min": dur,
                                                "duration_sec": duration_sec
                                            }
                                            break
                        except Exception as e:
                            LOGGER(__name__).error(f"❌ Error finding Spotify-style match: {e}")

                        # ADD TRACK TO DB & LOG
                        if recommendation:
                            db[chat_id].append({
                                "title": str(recommendation.get("title", "Unknown Title")),
                                "dur": recommendation.get("duration_min", "0:00"),
                                "streamtype": popped.get("streamtype", "audio") if popped else "audio",
                                "by": "❍ ʙʏ ➥ Spotify Radio 🟢",
                                "user_id": 0,
                                "chat_id": chat_id,
                                "file": f"vid_{recommendation.get('vidid', '')}",
                                "vidid": str(recommendation.get("vidid", "")),
                                "seconds": recommendation.get("duration_sec", 0),
                                "old_dur": recommendation.get("duration_min", "0:00"),
                                "old_second": 0,
                                "played": 0,
                                "client": popped.get("client", app)
                            })
                            
                            logger_id = getattr(config, "LOG_GROUP_ID", getattr(config, "LOGGER_ID", None))
                            if logger_id:
                                try:
                                    artist_or_lang = " / ".join(filter(None, [detected_artist, detected_lang]))
                                    if not artist_or_lang: artist_or_lang = "Algorithmic Radio"
                                        
                                    log_text = (
                                        f"📻 **Spotify-Style Radio Active**\n\n"
                                        f"**Group ID:** `{chat_id}`\n"
                                        f"**Seed Track:** `{raw_title}`\n"
                                        f"**Now Playing:** `{recommendation.get('title')}`\n"
                                        f"**Artist/Genre Focus:** `{artist_or_lang}`\n"
                                        f"**Vibe Focus:** `{detected_mood.title() if detected_mood else 'Auto-Match'}`"
                                    )
                                    
                                    bot_url = f"https://t.me/{app.username}" if app.username else "https://t.me/"
                                    group_url = f"https://t.me/c/{str(chat_id).replace('-100', '')}/1" if str(chat_id).startswith("-100") else bot_url

                                    reply_markup = InlineKeyboardMarkup([
                                        [
                                            InlineKeyboardButton("👥 Playing Group", url=group_url),
                                            InlineKeyboardButton(f"🤖 {app.name}", url=bot_url)
                                        ]
                                    ])

                                    await app.send_message(
                                        int(logger_id), 
                                        log_text,
                                        reply_markup=reply_markup
                                    )
                                except Exception as e:
                                    LOGGER(__name__).warning(f"Failed to send Autoplay Log to GC: {e}")
                        else:
                            LOGGER(__name__).warning(f"⚠️ Autoplay returned empty choices for chat: {chat_id}. Forcing cleanup.")

            if not db.get(chat_id): 
                await _clear_(chat_id)
                if chat_id in self.active_clients: del self.active_clients[chat_id]
                try: await client.leave_call(chat_id) 
                except: pass
                return

        except Exception as e:
            LOGGER(__name__).error(f"❌ Error inside change_stream execution framework: {e}")
            await _clear_(chat_id)
            if chat_id in self.active_clients: del self.active_clients[chat_id]
            try: await client.leave_call(chat_id) 
            except: pass
            return

        if db.get(chat_id):
            queued = db[chat_id][0]["file"]
            original_chat_id = db[chat_id][0]["chat_id"]
            streamtype = db[chat_id][0]["streamtype"]
            videoid = db[chat_id][0]["vidid"]
            chat_client = db[chat_id][0].get("client") or app

            db[chat_id][0]["played"] = 0
            exis = db[chat_id][0].get("old_dur")
            if exis:
                db[chat_id][0]["dur"] = exis
                db[chat_id][0]["seconds"] = db[chat_id][0]["old_second"]
                db[chat_id][0]["speed_path"] = None
                db[chat_id][0]["speed"] = 1.0
            video = True if str(streamtype) == "video" else False
            
            try:
                language = await get_lang(chat_id)
                _ = get_string(language)
            except:
                _ = get_string("en")
                
            if not db.get(chat_id): return
            
            raw_title = db[chat_id][0].get("title")
            title = str(raw_title).title() if raw_title else "Unknown Title"
            raw_user = db[chat_id][0].get("by")
            user = str(raw_user) if raw_user and str(raw_user).strip() else "Unknown User"
            user_id = db[chat_id][0].get("user_id", 0) 
            duration_str = db[chat_id][0].get("dur", "0:00")
            
            if "live_" in queued:
                n, link = await YouTube.video(videoid, True)
                if n == 0: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                try:
                    stream = self._build_stream(link, video=video)
                    await self._play_on_assistant(client, chat_id, stream)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                button = stream_markup(_, chat_id)
                try:
                    run = await chat_client.send_photo(
                        chat_id=original_chat_id, photo=get_random_img(config.STREAM_IMG_URL),
                        caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], duration_str, user),
                        reply_markup=InlineKeyboardMarkup(button)
                    )
                    if db.get(chat_id):
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "tg"
                except: pass
                
            elif "vid_" in queued:
                mystic = await chat_client.send_message(original_chat_id, _["call_7"])
                try:
                    file_path, direct = await YouTube.download(videoid, mystic, videoid=True, video=video)
                except:
                    try: file_path, direct = await YouTube.download(videoid, mystic, videoid=True, video=video)
                    except:
                        try: await mystic.edit_text("⚠️ **YouTube Timeout! Skipping...**", disable_web_page_preview=True)
                        except: pass
                        await asyncio.sleep(2)
                        return await self.change_stream(client, chat_id)
                
                if not file_path or str(file_path) == "None":
                    try: await mystic.edit_text("❌ **Error:** Download failed. Skipping track...")
                    except: pass
                    await asyncio.sleep(2)
                    return await self.change_stream(client, chat_id)

                try:
                    stream = self._build_stream(file_path, video=video)
                    await self._play_on_assistant(client, chat_id, stream)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                img = await gen_thumb(videoid, user_id, chat_client) or get_random_img(config.PLAYLIST_IMG_URL)
                button = stream_markup(_, chat_id)
                try: await mystic.delete()
                except: pass
                
                try:
                    run = await chat_client.send_photo(
                        chat_id=original_chat_id, photo=img,
                        caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], duration_str, user),
                        reply_markup=InlineKeyboardMarkup(button)
                    )
                    if db.get(chat_id):
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "stream"
                except: pass
                
            elif "index_" in queued:
                try:
                    stream = self._build_stream(videoid, video=video)
                    await self._play_on_assistant(client, chat_id, stream)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                button = stream_markup(_, chat_id)
                try:
                    run = await chat_client.send_photo(
                        chat_id=original_chat_id, photo=get_random_img(config.STREAM_IMG_URL),
                        caption=_["stream_2"].format(user), reply_markup=InlineKeyboardMarkup(button)
                    )
                    if db.get(chat_id):
                        db[chat_id][0]["mystic"] = run
                        db[chat_id][0]["markup"] = "tg"
                except: pass
                
            else:
                try:
                    stream = self._build_stream(queued, video=video)
                    await self._play_on_assistant(client, chat_id, stream)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                if videoid == "telegram":
                    button = stream_markup(_, chat_id)
                    tg_img = get_random_img(config.TELEGRAM_AUDIO_URL) if not video else get_random_img(config.TELEGRAM_VIDEO_URL)
                    try:
                        run = await chat_client.send_photo(
                            chat_id=original_chat_id, photo=tg_img,
                            caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], duration_str, user),
                            reply_markup=InlineKeyboardMarkup(button)
                        )
                        if db.get(chat_id):
                            db[chat_id][0]["mystic"] = run
                            db[chat_id][0]["markup"] = "tg"
                    except: pass
                    
                elif videoid in ["soundcloud", "spotify", "apple", "jiosaavn"]:
                    button = stream_markup(_, chat_id)
                    try:
                        run = await chat_client.send_photo(
                            chat_id=original_chat_id, photo=get_random_img(config.SOUNCLOUD_IMG_URL),
                            caption=_["stream_1"].format(config.SUPPORT_CHAT, title[:23], duration_str, user),
                            reply_markup=InlineKeyboardMarkup(button)
                        )
                        if db.get(chat_id):
                            db[chat_id][0]["mystic"] = run
                            db[chat_id][0]["markup"] = "tg"
                    except: pass
                    
                else:
                    img = await gen_thumb(videoid, user_id, chat_client) or get_random_img(config.PLAYLIST_IMG_URL)
                    button = stream_markup(_, chat_id)
                    try:
                        run = await chat_client.send_photo(
                            chat_id=original_chat_id, photo=img,
                            caption=_["stream_1"].format(f"https://t.me/{app.username}?start=info_{videoid}", title[:23], duration_str, user),
                            reply_markup=InlineKeyboardMarkup(button)
                        )
                        if db.get(chat_id):
                            db[chat_id][0]["mystic"] = run
                            db[chat_id][0]["markup"] = "stream"
                    except: pass

    async def ping(self):
        pings = []
        if getattr(config, "STRING1", None): pings.append(self.one.ping)
        if getattr(config, "STRING2", None): pings.append(self.two.ping)
        if getattr(config, "STRING3", None): pings.append(self.three.ping)
        if getattr(config, "STRING4", None): pings.append(self.four.ping)
        if getattr(config, "STRING5", None): pings.append(self.five.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Clients...\n")
        if getattr(config, "STRING1", None): await self.one.start()
        if getattr(config, "STRING2", None): await self.two.start()
        if getattr(config, "STRING3", None): await self.three.start()
        if getattr(config, "STRING4", None): await self.four.start()
        if getattr(config, "STRING5", None): await self.five.start()

    async def decorators(self):
        async def stream_handler(client, update):
            try:
                c_id = getattr(update, "chat_id", None)
                if not c_id: return
                
                t_name = type(update).__name__
                if "ChatUpdate" in t_name:
                    status = str(getattr(update, "status", "")).upper()
                    if "KICKED" in status or "LEFT" in status or "CLOSED" in status:
                        await self.stop_stream(c_id)
                elif "StreamEnd" in t_name:
                    await self.change_stream(client, c_id)
            except Exception as e:
                LOGGER(__name__).error(f"Stream handler error: {e}")

        if getattr(config, "STRING1", None): self.one.on_update()(stream_handler)
        if getattr(config, "STRING2", None): self.two.on_update()(stream_handler)
        if getattr(config, "STRING3", None): self.three.on_update()(stream_handler)
        if getattr(config, "STRING4", None): self.four.on_update()(stream_handler)
        if getattr(config, "STRING5", None): self.five.on_update()(stream_handler)

SHUKLA = Call()
