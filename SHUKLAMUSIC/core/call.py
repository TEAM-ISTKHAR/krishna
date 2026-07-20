import asyncio
import os
import random
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import ConnectionNotFound, TelegramServerError
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

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

    async def _prefetch_next(self, chat_id: int) -> None:
        if chat_id in self.autoplay_prefetching:
            return
        self.autoplay_prefetching.add(chat_id)
        try:
            await asyncio.sleep(3)
            check = db.get(chat_id)
            if check and len(check) > 1:
                return

            is_autoplay = await get_autoplay(chat_id)
            if is_autoplay and check:
                current_vidid = check[0].get("vidid")
                if current_vidid and current_vidid not in ["telegram", "soundcloud"]:
                    try:
                        related = await YouTube.get_related(current_vidid, self.history[chat_id])
                        if related:
                            self.pending_autoplay[chat_id] = related
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            self.autoplay_prefetching.discard(chat_id)

    def _build_stream(
        self,
        source: str,
        video: bool,
        ffmpeg: str | None = None,
    ) -> types.MediaStream:
        base_flags = "-threads 0"
        combined = f"{base_flags} {ffmpeg}" if ffmpeg else base_flags
        return types.MediaStream(
            media_path=source,
            audio_parameters=types.AudioQuality.MEDIUM,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if video
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=combined,
        )

    async def _play_on_assistant(
        self,
        client: PyTgCalls,
        chat_id: int,
        stream: types.MediaStream,
    ):
        try:
            await client.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=False),
            )
            asyncio.create_task(self._prefetch_next(chat_id))
        except exceptions.NoActiveGroupCall:
            raise
        except exceptions.NoAudioSourceFound:
            raise
        except (ConnectionNotFound, TelegramServerError):
            raise
        except Exception:
            raise

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
        for string, client in [
            (config.STRING1, self.one),
            (config.STRING2, self.two),
            (config.STRING3, self.three),
            (config.STRING4, self.four),
            (config.STRING5, self.five),
        ]:
            if not string:
                continue
            try:
                await client.leave_call(chat_id, close=False)
            except Exception:
                pass
        try:
            self.clear_autoplay(chat_id)
            await _clear_(chat_id)
        except Exception:
            pass

    async def speedup_stream(self, chat_id: int, file_path, speed, playing):
        assistant = await group_assistant(self, chat_id)
        if str(speed) != "1.0":
            base = os.path.basename(file_path)
            chatdir = os.path.join(os.getcwd(), "playback", str(speed))
            if not os.path.isdir(chatdir):
                os.makedirs(chatdir)
            out = os.path.join(chatdir, base)
            if not os.path.isfile(out):
                if str(speed) == "0.5":
                    vs = 2.0
                elif str(speed) == "0.75":
                    vs = 1.35
                elif str(speed) == "1.5":
                    vs = 0.68
                elif str(speed) == "2.0":
                    vs = 0.5
                else:
                    vs = 1.0
                proc = await asyncio.create_subprocess_shell(
                    cmd=(
                        "ffmpeg "
                        "-i "
                        f"{file_path} "
                        "-filter:v "
                        f"setpts={vs}*PTS "
                        "-filter:a "
                        f"atempo={speed} "
                        f"{out}"
                    ),
                    stdin=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
        else:
            out = file_path
        dur = await asyncio.get_event_loop().run_in_executor(None, check_duration, out)
        dur = int(dur)
        played, con_seconds = speed_converter(playing[0]["played"], speed)
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

    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        try:
            check = db.get(chat_id)
            check.pop(0)
        except Exception:
            pass
        self.clear_autoplay(chat_id)
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        try:
            await assistant.leave_call(chat_id, close=False)
        except Exception:
            pass
    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        stream = self._build_stream(link, video=bool(video))
        await self._play_on_assistant(assistant, chat_id, stream)

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        ffmpeg = f"-ss {to_seek} -to {duration}"
        video_mode = mode == "video"
        stream = self._build_stream(
            file_path,
            video=video_mode,
            ffmpeg=ffmpeg,
        )
        await self._play_on_assistant(assistant, chat_id, stream)

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOG_GROUP_ID)
        stream = self._build_stream(link, video=True)
        await self._play_on_assistant(assistant, config.LOG_GROUP_ID, stream)
        await asyncio.sleep(0.2)
        try:
            await assistant.leave_call(config.LOG_GROUP_ID, close=False)
        except Exception:
            pass

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        language = await get_lang(chat_id)
        _ = get_string(language)
        stream = self._build_stream(link, video=bool(video))
        try:
            await self._play_on_assistant(assistant, chat_id, stream)
        except exceptions.NoActiveGroupCall:
            raise AssistantErr(_["call_8"])
        except exceptions.NoAudioSourceFound:
            raise AssistantErr(_["call_10"])
        except (ConnectionNotFound, TelegramServerError):
            raise AssistantErr(_["call_10"])
        except Exception:
            raise AssistantErr(_["call_10"])
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)

    async def change_stream(self, client: PyTgCalls, chat_id: int):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            await auto_clean(popped)

            if not check:
                try:
                    is_autoplay = await get_autoplay(chat_id)
                except Exception:
                    is_autoplay = False

                if is_autoplay and popped:
                    vidid = popped.get("vidid")
                    if vidid and vidid not in ["telegram", "soundcloud"]:
                        self.history[chat_id].append(vidid)
                        del self.history[chat_id][:-20]

                        related = self.pending_autoplay.pop(chat_id, None)

                        if not related:
                            try:
                                raw_title = popped.get("title", "Unknown Title")
                                title_lower = str(raw_title).lower()
                                last_vidid = str(vidid)

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
                                    ]
                                }

                                ignore_artist_kws = ["hindi", "punjabi", "bhojpuri", "haryanvi"]
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
                                    if detected_mood:
                                        query_parts.append(detected_mood)
                                    random_modifiers = ["audio track", "lyrical", "best of", "hits", "new", "live", "unplugged"]
                                    query_parts.append(random.choice(random_modifiers))
                                    search_query = " ".join(query_parts)
                                else:
                                    clean_title = re.sub(r'[\[\(].*?[\]\)]', '', str(raw_title))
                                    clean_title = clean_title.split("|")[0].split("-")[0].split(",")[0].strip()
                                    fallback_modifiers = ["similar artists", "playlist", "radio mix", "hits"]
                                    search_query = f"{clean_title} {random.choice(fallback_modifiers)}"

                                use_vidid = last_vidid if random.randint(1, 10) <= 4 else None

                                try:
                                    recommendation = await YouTube.autoplay(last_vidid=use_vidid, title=search_query, max_duration=600)
                                    if recommendation:
                                        related = {
                                            "vidid": recommendation.get("vidid"),
                                            "title": recommendation.get("title", "Unknown Title"),
                                            "duration": recommendation.get("duration_min", "0:00"),
                                            "duration_sec": recommendation.get("duration_sec", 0),
                                        }
                                    else:
                                        related = None
                                except AttributeError:
                                    from py_yt import VideosSearch
                                    results = VideosSearch(search_query, limit=1)
                                    res = await results.next()
                                    if res and res.get("result"):
                                        track = res["result"][0]
                                        dur = track.get("duration", "0:00")
                                        parts = dur.split(":")
                                        duration_sec = sum(int(x) * 60 ** i for i, x in enumerate(reversed(parts)))
                                        related = {
                                            "vidid": track.get("id"),
                                            "title": track.get("title", "Unknown Title"),
                                            "duration": dur,
                                            "duration_sec": duration_sec
                                        }
                                    else:
                                        related = await YouTube.get_related(vidid, self.history[chat_id])
                            except Exception:
                                try:
                                    related = await YouTube.get_related(vidid, self.history[chat_id])
                                except Exception:
                                    related = None

                        if not related:
                            self.autoplay_failures[chat_id] += 1
                            if self.autoplay_failures[chat_id] >= 4:
                                try:
                                    await app.send_message(chat_id, "⚠️ Autoplay failed 4 times. Stopping stream.")
                                except: pass
                        else:
                            self.autoplay_failures[chat_id] = 0

                            # ✅ YAHAN "ʀєǫυєsᴛєʀ : Spotify Radio 🟢" ADD KIYA HAI
                            db[chat_id].append(
                                {
                                    "vidid": related["vidid"],
                                    "file": f"vid_{related['vidid']}",
                                    "title": related["title"],
                                    "by": "ʀєǫυєsᴛєʀ : Spotify Radio 🟢",
                                    "chat_id": popped.get("chat_id", chat_id),
                                    "streamtype": "audio",
                                    "dur": related.get("duration", "Unknown"),
                                    "seconds": related.get("duration_sec", 0),
                                }
                            )
                            try:
                                short_title = related["title"][:45] + "..." if len(related["title"]) > 45 else related["title"]
                                notice = await app.send_message(
                                    chat_id, 
                                    f"<blockquote>▶️ <b>Aᴜᴛᴏᴘʟᴀʏ Nᴇxᴛ :</b>\n🎧 <a href='https://youtube.com/watch?v={related['vidid']}'><i>{short_title}</i></a></blockquote>", 
                                    disable_web_page_preview=True
                                )
                                asyncio.create_task(_delete_msg(notice, 6))

                                if hasattr(config, "LOG_GROUP_ID") and config.LOG_GROUP_ID:
                                    matched_title = popped.get("title", "Unknown Track")[:45]
                                    log_text = (
                                        f"<blockquote><b>🔁 AUTO-PLAY TRACK STARTED</b>\n\n"
                                        f"<b>🥀 GROUP :</b> {chat_id}\n"
                                        f"<b>🎵 PLAYING :</b> <a href='https://youtube.com/watch?v={related['vidid']}'>{short_title}</a>\n"
                                        f"<b>🔗 MATCHED WITH :</b> {matched_title}\n"
                                        f"<b>⏭ UPCOMING :</b> Autoplay will decide next...</blockquote>"
                                    )
                                    await app.send_message(config.LOG_GROUP_ID, log_text, disable_web_page_preview=True)
                            except Exception:
                                pass

            if not check:
                self.clear_autoplay(chat_id)
                await _clear_(chat_id)
                return await client.leave_call(chat_id, close=False)
        except Exception:
            try:
                self.clear_autoplay(chat_id)
                await _clear_(chat_id)
                return await client.leave_call(chat_id, close=False)
            except Exception:
                return
        queued = check[0]["file"]
        language = await get_lang(chat_id)
        _ = get_string(language)
        title = (check[0]["title"]).title()
        user = check[0]["by"]
        original_chat_id = check[0]["chat_id"]
        streamtype = check[0]["streamtype"]
        videoid = check[0]["vidid"]
        db[chat_id][0]["played"] = 0
        exis = (check[0]).get("old_dur")

        if exis:
            db[chat_id][0]["dur"] = exis
            db[chat_id][0]["seconds"] = check[0]["old_second"]
            db[chat_id][0]["speed_path"] = None
            db[chat_id][0]["speed"] = 1.0

        video = True if str(streamtype) == "video" else False

        if "live_" in queued:
            n, link = await YouTube.video(videoid, True)
            if n == 0:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            stream = self._build_stream(link, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            img = await gen_thumb(videoid)
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

        elif "vid_" in queued:
            mystic = await app.send_message(original_chat_id, _["call_7"])
            try:
                file_path, direct = await YouTube.download(
                    videoid,
                    mystic,
                    videoid=True,
                    video=video,
                )
            except Exception:
                return await mystic.edit_text(
                    _["call_6"], disable_web_page_preview=True
                )
            stream = self._build_stream(file_path, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            img = await gen_thumb(videoid)
            button = stream_markup(_, chat_id)
            await mystic.delete()
            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=img,
                caption=_["stream_1"].format(
                    f"https://t.me/{app.username}?start=info_{videoid}",
                    title[:23],
                    check[0]["dur"],
                    user,
                ),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "stream"

        elif "index_" in queued:
            stream = self._build_stream(videoid, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            button = stream_markup(_, chat_id)
            run = await app.send_photo(
                chat_id=original_chat_id,
                photo=config.STREAM_IMG_URL,
                caption=_["stream_2"].format(user),
                reply_markup=InlineKeyboardMarkup(button),
            )
            db[chat_id][0]["mystic"] = run
            db[chat_id][0]["markup"] = "tg"

        else:
            stream = self._build_stream(queued, video=video)
            try:
                await self._play_on_assistant(client, chat_id, stream)
            except Exception:
                return await app.send_message(
                    original_chat_id,
                    text=_["call_6"],
                )
            if videoid == "telegram":
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=(
                        config.TELEGRAM_VIDEO_URL
                        if video
                        else config.TELEGRAM_AUDIO_URL
                    ),
                    caption=_["stream_1"].format(
                        config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            elif videoid == "soundcloud":
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=(
                        config.TELEGRAM_VIDEO_URL
                        if video
                        else config.SOUNCLOUD_IMG_URL
                    ),
                    caption=_["stream_1"].format(
                        config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "tg"
            else:
                img = await gen_thumb(videoid)
                button = stream_markup(_, chat_id)
                run = await app.send_photo(
                    chat_id=original_chat_id,
                    photo=img,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    reply_markup=InlineKeyboardMarkup(button),
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "stream"

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
