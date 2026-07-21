import asyncio
import os
import random
import logging
import re
from datetime import datetime, timedelta
from typing import Union

from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait  # Added to catch FloodWait specifically

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality

import config
from PritiMusic import LOGGER, YouTube, app
from PritiMusic.misc import db
from PritiMusic.utils.database import (
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
)
from PritiMusic.utils.exceptions import AssistantErr
from PritiMusic.utils.formatters import check_duration, seconds_to_min, speed_converter
from PritiMusic.utils.inline.play import stream_markup, telegram_markup
from PritiMusic.utils.stream.autoclear import auto_clean
from strings import get_string
from PritiMusic.utils.thumbnails import get_thumb

# ==========================================
# 🛑 GLOBAL ERROR HANDLER & STATE SYNC
# ==========================================
def handle_asyncio_exceptions(loop, context):
    msg = context.get("exception", context.get("message"))
    msg_str = str(msg).lower()
    
    expected_sync_events = [
        "groupcall_forbidden", 
        "setvideocallstatus", 
        "groupcall_invalid", 
        "no active group call", 
        "group call has already ended"
    ]
    
    if any(err in msg_str for err in expected_sync_events):
        logging.getLogger("asyncio").info(f"ℹ️ VC State Sync (Harmless): {msg}")
    else:
        logging.getLogger("asyncio").error(f"❌ Unhandled Asyncio Error: {msg}")

try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.get_event_loop()
loop.set_exception_handler(handle_asyncio_exceptions)

autoend = {}
counter = {}

FORCE_JOIN_LINKS = [
    "https://t.me/betabot_hub",
    "https://t.me/betabot_support",
    "https://t.me/sukoon_s",
]

def get_random_img(img_list):
    if img_list:
        if isinstance(img_list, list):
            return random.choice(img_list)
        return img_list
    return "https://telegra.ph/file/2e3d368e77c449c287430.jpg" 

async def _clear_(chat_id):
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)


class Call(PyTgCalls):
    def __init__(self):
        # Assistant 1
        self.userbot1 = Client(
            name="LuckyAss1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(self.userbot1, cache_duration=100)

        # Assistant 2
        self.two = None
        if getattr(config, "STRING2", None):
            self.userbot2 = Client(
                name="LuckyAss2",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=str(config.STRING2),
            )
            self.two = PyTgCalls(self.userbot2, cache_duration=100)

        # Assistant 3
        self.three = None
        if getattr(config, "STRING3", None):
            self.userbot3 = Client(
                name="LuckyAss3",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=str(config.STRING3),
            )
            self.three = PyTgCalls(self.userbot3, cache_duration=100)

        # Assistant 4
        self.four = None
        if getattr(config, "STRING4", None):
            self.userbot4 = Client(
                name="LuckyAss4",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=str(config.STRING4),
            )
            self.four = PyTgCalls(self.userbot4, cache_duration=100)

        # Assistant 5
        self.five = None
        if getattr(config, "STRING5", None):
            self.userbot5 = Client(
                name="LuckyAss5",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=str(config.STRING5),
            )
            self.five = PyTgCalls(self.userbot5, cache_duration=100)

        self.custom_assistants = {} 
        self.active_clients = {} 

    async def _safe_change_stream(self, client, chat_id, file_path, video=False, extra_args=""):
        if not video:
            stream = MediaStream(file_path, audio_parameters=AudioQuality.HIGH, ffmpeg_parameters=extra_args)
            await client.play(chat_id, stream)
            return

        try: 
            stream = MediaStream(
                file_path, 
                audio_parameters=AudioQuality.HIGH, 
                video_parameters=VideoQuality.HD_720p, 
                ffmpeg_parameters=extra_args
            )
            await client.play(chat_id, stream)
        except Exception as e:
            LOGGER(__name__).warning(f"720p Change Stream failed, auto-switching to 480p: {e}")
            stream = MediaStream(
                file_path, 
                audio_parameters=AudioQuality.HIGH, 
                video_parameters=VideoQuality.SD_480p, 
                ffmpeg_parameters=extra_args
            )
            await client.play(chat_id, stream)

    async def _safe_join_call(self, assistant_to_join, chat_id, file_path, video=False):
        if not video:
            stream = MediaStream(file_path, audio_parameters=AudioQuality.HIGH)
            return await assistant_to_join.play(chat_id, stream)

        try: 
            stream = MediaStream(
                file_path, 
                audio_parameters=AudioQuality.HIGH, 
                video_parameters=VideoQuality.HD_720p
            )
            await assistant_to_join.play(chat_id, stream)
        except Exception as e:
            LOGGER(__name__).warning(f"720p Join Call failed, auto-switching to 480p: {e}")
            stream = MediaStream(
                file_path, 
                audio_parameters=AudioQuality.HIGH, 
                video_parameters=VideoQuality.SD_480p
            )
            await assistant_to_join.play(chat_id, stream)

    async def get_active_clients(self, chat_id):
        clients = []
        if chat_id in self.active_clients:
            val = self.active_clients[chat_id]
            if isinstance(val, list):
                clients.extend(val)
            else:
                clients.append(val)
        if not clients:
            try:
                main_ass = await group_assistant(self, chat_id)
                clients.append(main_ass)
            except:
                clients.append(self.one)
        return list(set(clients))

    async def pause_stream(self, chat_id: int, assistant_type=None):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try: await assistant.pause_stream(chat_id)
            except: pass

    async def resume_stream(self, chat_id: int, assistant_type=None):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try: await assistant.resume_stream(chat_id)
            except: pass

    async def stop_stream(self, chat_id: int, assistant_type=None):
        try: chat_id = int(chat_id)
        except: pass
            
        try: await _clear_(chat_id)
        except: pass
        
        active_assistants = await self.get_active_clients(chat_id)
        for assistant in active_assistants:
            if assistant:
                try: 
                    await assistant.leave_call(chat_id)
                    LOGGER(__name__).info(f"✅ Assistant left VC successfully in chat {chat_id}.")
                except Exception as e: 
                    error_msg = str(e).lower()
                    ignore_list = ["no active group call", "already ended", "not in a call", "groupcall_forbidden", "groupcall_invalid"]
                    if any(ign in error_msg for ign in ignore_list):
                        LOGGER(__name__).info(f"ℹ️ Assistant State Sync: VC already closed in {chat_id}.")
                    else:
                        LOGGER(__name__).error(f"❌ Assistant failed to leave VC in {chat_id}: {e}")
                    
        if chat_id in self.active_clients: 
            del self.active_clients[chat_id]

    async def stop_stream_force(self, chat_id: int):
        try: chat_id = int(chat_id)
        except: pass
            
        active_assistants = await self.get_active_clients(chat_id)
        for assistant in active_assistants:
            if assistant:
                try: 
                    await assistant.leave_call(chat_id)
                except Exception as e: 
                    error_msg = str(e).lower()
                    ignore_list = ["no active group call", "already ended", "not in a call", "groupcall_forbidden", "groupcall_invalid"]
                    if any(ign in error_msg for ign in ignore_list):
                        LOGGER(__name__).info(f"ℹ️ Assistant State Sync: VC already closed in {chat_id} (Force).")
                    else:
                        LOGGER(__name__).error(f"❌ Assistant force-leave failed in {chat_id}: {e}")
                    
        if chat_id in self.active_clients: 
            del self.active_clients[chat_id]
            
        try: await _clear_(chat_id)
        except: pass

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistants = await self.get_active_clients(chat_id)
        assistant = assistants[0] if assistants else self.one
        if str(speed) != str("1.0"):
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                if str(speed) == str("0.5"): vs = 2.0
                if str(speed) == str("0.75"): vs = 1.35
                if str(speed) == str("1.5"): vs = 0.68
                if str(speed) == str("2.0"): vs = 0.5
                proc = await asyncio.create_subprocess_shell(
                    cmd=(f"ffmpeg -i {file_path} -filter:v setpts={vs}*PTS -filter:a atempo={speed} {out}"),
                    stdin=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path
            
        try: loop = asyncio.get_running_loop()
        except RuntimeError: loop = asyncio.get_event_loop()
            
        dur = await loop.run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration = seconds_to_min(dur)
        
        is_video = playing[0]["streamtype"] == "video"
        extra_args = f"-ss {played} -to {duration}"
        
        if str(db[chat_id][0]["file"]) == str(file_path):
            for assistant in assistants:
                try: await self._safe_change_stream(assistant, chat_id, out, is_video, extra_args)
                except: pass
        else: raise AssistantErr("Umm\n\n**Need Help Join - @betabot_support**")
        
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

    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None, assistant_type=None):
        assistants = await self.get_active_clients(chat_id)
        for assistant in assistants:
            try: await self._safe_change_stream(assistant, chat_id, link, video)
            except: pass

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistants = await self.get_active_clients(chat_id)
        is_video = mode == "video"
        extra_args = f"-ss {to_seek} -to {duration}"
        for assistant in assistants:
            try: await self._safe_change_stream(assistant, chat_id, file_path, is_video, extra_args)
            except: pass

    async def join_call(self, chat_id: int, original_chat_id: int, link, video: Union[bool, str] = None, image: Union[bool, str] = None, userbot=None):
        assistant_to_join = None
        if userbot:
            if FORCE_JOIN_LINKS:
                for link_join in FORCE_JOIN_LINKS:
                    try:
                        await userbot.join_chat(link_join)
                        await asyncio.sleep(0.5) 
                    except: pass
            user_id = userbot.me.id
            if user_id in self.custom_assistants:
                assistant_to_join = self.custom_assistants[user_id]
            else:
                assistant_to_join = PyTgCalls(userbot, cache_duration=100)
                
                @assistant_to_join.on_update()
                async def clone_stream_handler(client, update):
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
                        LOGGER(__name__).error(f"❌ Clone stream handler exception: {e}")

                await assistant_to_join.start()
                self.custom_assistants[user_id] = assistant_to_join
        else:
            assistant_to_join = await group_assistant(self, chat_id)
            
        if chat_id not in self.active_clients:
            self.active_clients[chat_id] = []
        if assistant_to_join not in self.active_clients[chat_id]:
            self.active_clients[chat_id].append(assistant_to_join)
            
        try:
            await self._safe_join_call(assistant_to_join, chat_id, link, video)
        except FloodWait as e:
            LOGGER(__name__).warning(f"FloodWait hit! Sleeping for {e.value} seconds before retrying VC join...")
            await asyncio.sleep(e.value + 1)
            try:
                await self._safe_join_call(assistant_to_join, chat_id, link, video)
            except Exception as err:
                raise AssistantErr(f"VC Error after retry: {err} - (Please check if Voice Chat is turned on in the group)\n\n**Need Help Join - @betabot_support**")
        except Exception as e: 
            raise AssistantErr(f"VC Error: {e} - (Please check if Voice Chat is turned on in the group)\n\n**Need Help Join - @betabot_support**")
        
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video: await add_active_video_chat(chat_id)
        
        if await is_autoend(chat_id):
            counter[chat_id] = {}
            try:
                users = len(await assistant_to_join.get_participants(chat_id))
                if users == 1:
                    autoend[chat_id] = datetime.now() + timedelta(minutes=1)
            except: pass

    async def change_stream(self, client, chat_id):
        # 🟢 ROUTING FIX
        active_assistants = await self.get_active_clients(chat_id)
        client = active_assistants[0] if active_assistants else client

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
            
            if not check:
                from PritiMusic.utils.database.autoplay import is_autoplay_group
                auto_on = await is_autoplay_group(chat_id)
                if auto_on and popped:
                    LOGGER(__name__).info(f"🔄 Spotify-Style Autoplay triggered for {chat_id}")
                    raw_title = popped.get("title", "Unknown Title")
                    title_lower = str(raw_title).lower()
                    last_vidid = str(popped.get("vidid", ""))

                    try:
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

                        detected_lang = None
                        detected_artist = None
                        detected_mood = None
                        
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

                        # 🟢 SPOTIFY RADIO STYLE QUERY BUILDER
                        query_parts = []

                        # Spotify Logic: Same Artist (70% chance) ya Same Language ka New Artist (30% chance)
                        if detected_lang:
                            available_singers = [s for s in keywords_map[detected_lang] if s not in ignore_artist_kws]
                            
                            # Randomly decide to stick with artist or switch
                            if detected_artist and random.randint(1, 10) <= 7:
                                query_parts.append(detected_artist)
                            elif available_singers:
                                new_singer = random.choice(available_singers).title()
                                query_parts.append(new_singer)
                                detected_artist = new_singer  # Logs ke liye naam update kar diya
                        elif detected_artist:
                            query_parts.append(detected_artist)
                            
                        if query_parts:
                            if detected_mood:
                                query_parts.append(detected_mood)
                                
                            # Repeat issue fix: Har baar search query ko alag banane ke liye random modifier
                            random_modifiers = ["audio track", "lyrical", "best of", "hits", "new", "live", "unplugged"]
                            query_parts.append(random.choice(random_modifiers))
                            search_query = " ".join(query_parts)
                        else:
                            # 🚨 REPEAT FIX FOR UNKNOWN ARTISTS (Like Sheheryar Rehan)
                            # Yeh extra kachra (jaise " | Music Video", "- Visual Galaxy") hata dega
                            clean_title = re.sub(r'[\[\(].*?[\]\)]', '', str(raw_title))
                            clean_title = clean_title.split("|")[0].split("-")[0].split(",")[0].strip()
                            
                            # Exact song mashup ko block karne ke liye fresh modifiers
                            fallback_modifiers = ["similar artists", "playlist", "radio mix", "hits"]
                            search_query = f"{clean_title} {random.choice(fallback_modifiers)}"
                            
                            detected_artist = "Smart Fallback"

                        # 🚨 CRITICAL LOOP BREAKER
                        # Agar YouTube ek hi song par loop ho raha hai, toh hum last_vidid 
                        # hata denge taaki algorithm fresh random search kare.
                        use_vidid = last_vidid if random.randint(1, 10) <= 4 else None

                        # max_duration 600 (10 mins) set hai taaki 1-hour jukeboxes na bajne lage
                        recommendation = await YouTube.autoplay(last_vidid=use_vidid, title=search_query, max_duration=600) 
                        
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
                                    if not artist_or_lang:
                                        artist_or_lang = "Algorithmic Radio"
                                        
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
                            LOGGER(__name__).warning(f"⚠️ YouTube Autoplay returned empty choices for chat: {chat_id}. Forcing cleanup.")
                    except Exception as e:
                        LOGGER(__name__).error(f"❌ Critical Autoplay exception processing track query: {e}")

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
                
                try: await self._safe_change_stream(client, chat_id, link, video)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                button = telegram_markup(_, chat_id)
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

                try: await self._safe_change_stream(client, chat_id, file_path, video)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                img = await get_thumb(videoid, user_id, chat_client) or get_random_img(config.PLAYLIST_IMG_URL)
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
                try: await self._safe_change_stream(client, chat_id, videoid, video)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                button = telegram_markup(_, chat_id)
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
                try: await self._safe_change_stream(client, chat_id, queued, video)
                except: return await chat_client.send_message(original_chat_id, text=_["call_6"])
                
                if videoid == "telegram":
                    button = telegram_markup(_, chat_id)
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
                    button = telegram_markup(_, chat_id)
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
                    img = await get_thumb(videoid, user_id, chat_client) or get_random_img(config.PLAYLIST_IMG_URL)
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

Lucky = Call() ya wala autoplay feature sukla mai set kro
