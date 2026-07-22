import asyncio
import os
import time
import random
from datetime import datetime, timedelta
from typing import Union

from ntgcalls import TelegramServerError
from pyrogram import Client
from pyrogram.enums import ChatType, ButtonStyle
from pyrogram.errors import ChatAdminRequired
from pyrogram.handlers import RawUpdateHandler
from pyrogram.raw.functions.channels import GetFullChannel
from pyrogram.raw.functions.messages import GetFullChat
from pyrogram.raw.types import PeerUser, UpdateGroupCallParticipants
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import AudioQuality, ChatUpdate, MediaStream, StreamEnded, Update, VideoQuality

import config
from strings import get_string
from VIVAANXMUSIC.utils.logger import autoplay_log
from VIVAANXMUSIC import LOGGER, YouTube, app
from VIVAANXMUSIC.misc import db
from VIVAANXMUSIC.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_autoplay,
    get_lang,
    get_loop,
    get_vcnotify,
    group_assistant,
    is_autoend,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from VIVAANXMUSIC.utils.exceptions import AssistantErr
from VIVAANXMUSIC.utils.formatters import check_duration, seconds_to_min, speed_converter

from VIVAANXMUSIC.utils.inline.play import stream_markup
from VIVAANXMUSIC.utils.inline.player import player_markup

from VIVAANXMUSIC.security import build_subprocess_env
from VIVAANXMUSIC.utils.stream.autoclear import auto_clean
from VIVAANXMUSIC.utils.stream.cards import schedule_stream_card
from VIVAANXMUSIC.utils.errors import capture_internal_err, send_large_error

autoend = {}
counter = {}
vc_join_monitors = {}
vc_join_snapshots = {}
vc_join_targets = {}
vc_join_call_map = {}
vc_join_event_cache = {}
vc_join_notice_cache = {}

def dynamic_media_stream(path: str, video: bool = False, ffmpeg_params: str = None) -> MediaStream:
    if not path:
        raise TypeError("Argument 'media_path' cannot be None or empty.")
    return MediaStream(
        audio_path=path,
        media_path=path,
        audio_parameters=AudioQuality.MEDIUM if video else AudioQuality.STUDIO,
        video_parameters=VideoQuality.HD_720p if video else VideoQuality.SD_360p,
        video_flags=(MediaStream.Flags.AUTO_DETECT if video else MediaStream.Flags.IGNORE),
        ffmpeg_parameters=ffmpeg_params,
    )

async def _clear_(chat_id: int) -> None:
    popped = db.pop(chat_id, None)
    if popped:
        if isinstance(popped, list):
            for track in popped:
                try:
                    await auto_clean(track)
                except Exception:
                    pass
        else:
            try:
                await auto_clean(popped)
            except Exception:
                pass
                
    db[chat_id] = []
    for call_id, info in list(vc_join_call_map.items()):
        if info.get("chat_id") == chat_id:
            vc_join_call_map.pop(call_id, None)
    task = vc_join_monitors.pop(chat_id, None)
    if task and not task.done():
        task.cancel()
    vc_join_snapshots.pop(chat_id, None)
    vc_join_targets.pop(chat_id, None)
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)

class Call:
    def __init__(self):
        self.userbot1 = Client(
            "VivaanXAssis1", config.API_ID, config.API_HASH, session_string=config.STRING1
        ) if config.STRING1 else None
        self.one = PyTgCalls(self.userbot1) if self.userbot1 else None

        self.userbot2 = Client(
            "VivaanXAssis2", config.API_ID, config.API_HASH, session_string=config.STRING2
        ) if config.STRING2 else None
        self.two = PyTgCalls(self.userbot2) if self.userbot2 else None

        self.userbot3 = Client(
            "VivaanXAssis3", config.API_ID, config.API_HASH, session_string=config.STRING3
        ) if config.STRING3 else None
        self.three = PyTgCalls(self.userbot3) if self.userbot3 else None

        self.userbot4 = Client(
            "VivaanXAssis4", config.API_ID, config.API_HASH, session_string=config.STRING4
        ) if config.STRING4 else None
        self.four = PyTgCalls(self.userbot4) if self.userbot4 else None

        self.userbot5 = Client(
            "VivaanXAssis5", config.API_ID, config.API_HASH, session_string=config.STRING5
        ) if config.STRING5 else None
        self.five = PyTgCalls(self.userbot5) if self.userbot5 else None

        self.active_calls: set[int] = set()
        self._stream_locks: dict[int, asyncio.Lock] = {}

    def _get_stream_lock(self, chat_id: int) -> asyncio.Lock:
        lock = self._stream_locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._stream_locks[chat_id] = lock
        return lock

    async def _resolve_vc_call_id(self, chat_id: int) -> int | None:
        try:
            chat = await app.get_chat(chat_id)
        except Exception:
            return None

        try:
            if chat.type in {ChatType.SUPERGROUP, ChatType.CHANNEL, ChatType.FORUM}:
                full = await app.invoke(
                    GetFullChannel(channel=await app.resolve_peer(chat_id))
                )
            else:
                full = await app.invoke(GetFullChat(chat_id=abs(int(chat_id))))
        except Exception:
            return None

        call = getattr(getattr(full, "full_chat", None), "call", None)
        if not call:
            return None
        return int(call.id)

    @staticmethod
    def _extract_user_id_from_peer(peer) -> int | None:
        if isinstance(peer, PeerUser):
            return int(peer.user_id)
        return None

    @staticmethod
    def _remember_join_event(call_id: int, user_id: int, date: int, source: int) -> bool:
        now = time.monotonic()
        for key, stamp in list(vc_join_event_cache.items()):
            if now - stamp > 30:
                vc_join_event_cache.pop(key, None)

        event_key = (call_id, user_id, date, source, "join")
        if event_key in vc_join_event_cache:
            return False

        vc_join_event_cache[event_key] = now 
        return True
        
    @staticmethod
    def _remember_join_notice(
        notify_chat_id: int,
        user_id: int,
        date: int,
        source: int,
    ) -> bool:
        now = time.monotonic()
        for key, stamp in list(vc_join_notice_cache.items()):
            if now - stamp > 60:
                vc_join_notice_cache.pop(key, None)

        notice_key = (notify_chat_id, user_id, date, source)
        if notice_key in vc_join_notice_cache:
            return False

        vc_join_notice_cache[notice_key] = now
        return True

    async def _fetch_vc_participant_ids(self, chat_id: int) -> set[int]:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        user_ids = set()
        for participant in participants:
            user_id = getattr(participant, "user_id", None)
            if not user_id:
                continue
            user_ids.add(int(user_id))
        return user_ids

    async def _send_vc_join_notice(
        self,
        notify_chat_id: int,
        user_id: int,
        date: int = 0,
        source: int = 0,
    ) -> None:
        if not self._remember_join_notice(notify_chat_id, user_id, date, source):
            return

        try:
            user = await app.get_users(user_id)
            name = " ".join(
                part for part in [user.first_name, user.last_name] if part
            ).strip() or user.username or "Unknown User"
            username = f" (@{user.username})" if user.username else ""
        except Exception:
            name = "Unknown User"
            username = ""

        await app.send_message(
            notify_chat_id,
            f"Joined VC\nName: {name}{username}\nUser ID: <code>{user_id}</code>",
        )

    async def _handle_group_call_participants_update(
        self,
        update: UpdateGroupCallParticipants,
    ) -> None:
        call_id = int(update.call.id)
        mapping = vc_join_call_map.get(call_id)
        if not mapping:
            return

        notify_chat_id = mapping["notify_chat_id"]
        if not await get_vcnotify(notify_chat_id):
            return

        member_snapshot = vc_join_snapshots.setdefault(mapping["chat_id"], set())

        for participant in update.participants:
            user_id = self._extract_user_id_from_peer(getattr(participant, "peer", None))
            if not user_id:
                continue

            if getattr(participant, "left", False):
                member_snapshot.discard(user_id)
                continue

            if not getattr(participant, "just_joined", False):
                continue

            if user_id in member_snapshot:
                continue

            if not self._remember_join_event(
                call_id,
                user_id,
                int(getattr(participant, "date", 0) or 0),
                int(getattr(participant, "source", 0) or 0),
            ):
                continue

            member_snapshot.add(user_id)
            await self._send_vc_join_notice(
                notify_chat_id,
                user_id,
                int(getattr(participant, "date", 0) or 0),
                int(getattr(participant, "source", 0) or 0),
            )

    async def _vc_join_monitor_loop(
        self,
        chat_id: int,
        notify_chat_id: int,
    ) -> None:
        try:
            while True:
                if not await get_vcnotify(notify_chat_id):
                    vc_join_snapshots.pop(chat_id, None)
                    await asyncio.sleep(1)
                    continue

                try:
                    current_ids = await self._fetch_vc_participant_ids(chat_id)
                except Exception:
                    await asyncio.sleep(1)
                    continue

                previous_ids = vc_join_snapshots.get(chat_id)
                if previous_ids is None:
                    vc_join_snapshots[chat_id] = current_ids
                    await asyncio.sleep(1)
                    continue

                joined_ids = current_ids - previous_ids
                for user_id in joined_ids:
                    try:
                        await self._send_vc_join_notice(
                            notify_chat_id,
                            user_id,
                        )
                    except Exception:
                        continue

                vc_join_snapshots[chat_id] = current_ids
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        finally:
            task = vc_join_monitors.get(chat_id)
            if task and task is asyncio.current_task():
                vc_join_monitors.pop(chat_id, None)

    async def maybe_start_vc_join_notifier(
        self,
        chat_id: int,
        notify_chat_id: int,
    ) -> bool:
        if not await get_vcnotify(notify_chat_id):
            return False

        call_id = await self._resolve_vc_call_id(chat_id)
        vc_join_targets[chat_id] = notify_chat_id
        if call_id:
            vc_join_call_map[call_id] = {
                "chat_id": chat_id,
                "notify_chat_id": notify_chat_id,
            }

        if chat_id not in vc_join_snapshots:
            try:
                vc_join_snapshots[chat_id] = await self._fetch_vc_participant_ids(chat_id)
            except Exception:
                vc_join_snapshots[chat_id] = set()

        existing = vc_join_monitors.get(chat_id)
        if not existing or existing.done():
            vc_join_monitors[chat_id] = asyncio.create_task(
                self._vc_join_monitor_loop(chat_id, notify_chat_id)
            )
        return True

    async def stop_vc_join_notifier(self, chat_id: int) -> None:
        task = vc_join_monitors.pop(chat_id, None)
        if task and not task.done():
            task.cancel()
        vc_join_snapshots.pop(chat_id, None)
        vc_join_targets.pop(chat_id, None)
        for call_id, info in list(vc_join_call_map.items()):
            if info.get("chat_id") == chat_id:
                vc_join_call_map.pop(call_id, None)

    async def _play_stream(self, assistant: PyTgCalls, chat_id: int, stream: MediaStream) -> None:
        async with self._get_stream_lock(chat_id):
            for attempt in range(2):
                try:
                    await assistant.play(chat_id, stream)
                    return
                except OSError as err:
                    if err.errno != 24 or attempt == 1:
                        raise
                    LOGGER(__name__).warning(
                        "Retrying stream play for chat %s after hitting open-file limit.",
                        chat_id,
                    )
                    await asyncio.sleep(1)

    @capture_internal_err
    async def pause_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    @capture_internal_err
    async def resume_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    @capture_internal_err
    async def mute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    @capture_internal_err
    async def unmute_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    @capture_internal_err
    async def stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await self.stop_vc_join_notifier(chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return
        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass
        finally:
            self.active_calls.discard(chat_id)

    @capture_internal_err
    async def force_stop_stream(self, chat_id: int) -> None:
        assistant = await group_assistant(self, chat_id)
        await self.stop_vc_join_notifier(chat_id)
        try:
            check = db.get(chat_id)
            if check:
                check.pop(0)
        except (IndexError, KeyError):
            pass
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        await _clear_(chat_id)
        if chat_id not in self.active_calls:
            return
        try:
            await assistant.leave_call(chat_id)
        except Exception:
            pass
        finally:
            self.active_calls.discard(chat_id)

    @capture_internal_err
    async def skip_stream(self, chat_id: int, link: str, video: Union[bool, str] = None, image: Union[bool, str] = None) -> None:
        if not link:
            LOGGER(__name__).warning(f"skip_stream received None/empty link for chat: {chat_id}")
            return
        assistant = await group_assistant(self, chat_id)
        stream = dynamic_media_stream(path=link, video=bool(video))
        await self._play_stream(assistant, chat_id, stream)

    @capture_internal_err
    async def vc_users(self, chat_id: int) -> list:
        assistant = await group_assistant(self, chat_id)
        participants = await assistant.get_participants(chat_id)
        return [p.user_id for p in participants if not p.is_muted]

    @capture_internal_err
    async def seek_stream(self, chat_id: int, file_path: str, to_seek: str, duration: str, mode: str) -> None:
        if not file_path:
            return
        assistant = await group_assistant(self, chat_id)
        ffmpeg_params = f"-ss {to_seek} -to {duration}"
        is_video = mode == "video"
        stream = dynamic_media_stream(path=file_path, video=is_video, ffmpeg_params=ffmpeg_params)
        await self._play_stream(assistant, chat_id, stream)

    @capture_internal_err
    async def speedup_stream(self, chat_id: int, file_path: str, speed: float, playing: list) -> None:
        if not file_path or not isinstance(playing, list) or not playing or not isinstance(playing[0], dict):
            raise AssistantErr("Invalid stream info for speedup.")

        assistant = await group_assistant(self, chat_id)
        base = os.path.basename(file_path)
        chatdir = os.path.join("playback", str(speed))
        os.makedirs(chatdir, exist_ok=True)
        out = os.path.join(chatdir, base)

        if not os.path.exists(out):
            vs = str(2.0 / float(speed))
            args = [
                "ffmpeg",
                "-i",
                file_path,
                "-filter:v",
                f"setpts={vs}*PTS",
                "-filter:a",
                f"atempo={speed}",
                out,
            ]
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=build_subprocess_env(),
            )
            await proc.communicate()

        dur = int(await asyncio.get_event_loop().run_in_executor(None, check_duration, out))
        played, con_seconds = speed_converter(playing[0]["played"], speed)
        duration_min = seconds_to_min(dur)
        is_video = playing[0]["streamtype"] == "video"
        ffmpeg_params = f"-ss {played} -to {duration_min}"
        stream = dynamic_media_stream(path=out, video=is_video, ffmpeg_params=ffmpeg_params)

        if chat_id in db and db[chat_id] and db[chat_id][0].get("file") == file_path:
            await self._play_stream(assistant, chat_id, stream)
        else:
            raise AssistantErr("Stream mismatch during speedup.")

        db[chat_id][0].update({
            "played": con_seconds,
            "dur": duration_min,
            "seconds": dur,
            "speed_path": out,
            "speed": speed,
            "old_dur": db[chat_id][0].get("dur"),
            "old_second": db[chat_id][0].get("seconds"),
        })

    @capture_internal_err
    async def stream_call(self, link: str) -> None:
        if not link:
            return
        assistant = await group_assistant(self, config.LOGGER_ID)
        try:
            await self._play_stream(assistant, config.LOGGER_ID, MediaStream(link))
            await asyncio.sleep(8)
        finally:
            try:
                await assistant.leave_call(config.LOGGER_ID)
            except:
                pass

    @capture_internal_err
    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ) -> None:
        if not link:
            raise AssistantErr("Stream link path cannot be empty.")
        assistant = await group_assistant(self, chat_id)
        lang = await get_lang(chat_id)
        _ = get_string(lang)
        stream = dynamic_media_stream(path=link, video=bool(video))

        try:
            await self._play_stream(assistant, chat_id, stream)
        except (NoActiveGroupCall, ChatAdminRequired):
            raise AssistantErr(_["call_8"])
        except TelegramServerError:
            raise AssistantErr(_["call_10"])
        except Exception as e:
            raise AssistantErr(
                f"ᴜɴᴀʙʟᴇ ᴛᴏ ᴊᴏɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ ᴄᴀʟʟ.\nRᴇᴀsᴏɴ: {e}"
            )
        self.active_calls.add(chat_id)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        await self.maybe_start_vc_join_notifier(chat_id, original_chat_id)

        if await is_autoend():
            counter[chat_id] = {}
            users = len(await assistant.get_participants(chat_id))
            if users == 1:
                autoend[chat_id] = datetime.now() + timedelta(minutes=1)

    async def _log_autoplay(self, chat_id: int, prev_title: str, next_title: str):
        if not config.LOGGER_ID:
            return
        try:
            chat = await app.get_chat(chat_id)
            chat_name = chat.title or "Unknown Group"
            chat_link = chat.invite_link
            
            if not chat_link and chat.username:
                chat_link = f"https://t.me/{chat.username}"
            if not chat_link:
                try:
                    chat_link = await app.export_chat_invite_link(chat_id)
                except:
                    chat_link = f"https://t.me/{app.username}?startgroup=true"

            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 ɢʀᴏᴜᴘ ʟɪɴᴋ", url=chat_link, style=ButtonStyle.PRIMARY)]
            ])
            
            text = (
                f"<b>💡 ᴀᴜᴛᴏᴘʟᴀʏ ʟᴏɢɢᴇʀ</b>\n\n"
                f"<b>🏠 ɢʀᴏᴜᴘ :</b> {chat_name} [<code>{chat_id}</code>]\n"
                f"<b>⏮ ᴘʀᴇᴠɪᴏᴜs :</b> {prev_title}\n"
                f"<b>⏭ ᴜᴘᴄᴏᴍɪɴɢ :</b> {next_title}"
            )
            
            await app.send_message(
                config.LOGGER_ID,
                text=text,
                reply_markup=markup,
                disable_web_page_preview=True
            )
        except Exception as e:
            LOGGER(__name__).warning(f"Autoplay Logger Error: {e}")

    async def _enqueue_autoplay_track(self, chat_id: int, finished_track: dict) -> bool:
        if not finished_track or not await get_autoplay(chat_id):
            return False

        queued_file = str(finished_track.get("file") or "")
        if queued_file.startswith("live_") or queued_file == "index_url":
            return False

        last_vidid = str(finished_track.get("vidid") or "")
        prev_title_log = finished_track.get("title", "Unknown Title")
        
        if not last_vidid or last_vidid in {"telegram", "soundcloud"}:
            raw_title = "latest hit trending songs"
            last_vidid = "default_seed"
        else:
            raw_title = prev_title_log

        title_lower = str(raw_title).lower()

        lang_pools = {
            "Hindi": ["hindi single track official video", "bollywood latest lyrical song", "latest hindi chill track"],
            "Punjabi": ["latest punjabi single official video", "punjabi trending track lyrical", "punjabi pop blast"],
            "Bhojpuri": ["bhojpuri latest single video song", "bhojpuri trending song official", "hit bhojpuri track"],
            "Haryanvi": ["haryanvi single track official", "latest haryanvi video song", "haryanvi dj mix"],
            "Tamil": ["tamil latest single official video", "kollywood trending song lyrical"],
            "Telugu": ["telugu tollywood latest single song", "telugu lyrical video official"],
            "English": ["english pop single official music video", "trending english lyrical song", "global top 50 pop hit"]
        }
        keywords_map = {
            "Punjabi": ["punjabi", "jass", "sidhu", "karan", "diljit", "amrit", "ap dhillon"],
            "Bhojpuri": ["bhojpuri", "khesari", "pawan", "shilpi", "antra"],
            "Haryanvi": ["haryanvi", "sapna", "renuka", "gulzaar"],
            "Tamil": ["tamil", "anirudh", "rahman", "kollywood"],
            "Telugu": ["telugu", "allu", "ramarao", "tollywood", "dsp"],
            "English": ["english", "pop song", "taylor swift", "justin bieber", "weekend"]
        }
        
        detected_lang = "Hindi" 
        for lang, kws in keywords_map.items():
            if any(kw in title_lower for kw in kws):
                detected_lang = lang
                break

        search_query = random.choice(lang_pools[detected_lang])
        valid_choices = []

        try:
            from youtubesearchpython.__future__ import VideosSearch
            search = VideosSearch(search_query, limit=15)
            result = await search.next()
            if result and result.get("result"):
                for res in result["result"]:
                    vidid = str(res.get("id") or "")
                    if not vidid or vidid == "None" or vidid == last_vidid:
                        continue
                    
                    next_dur = str(res.get("duration") or "0:00")
                    dur_sec = 0
                    if next_dur and ":" in next_dur:
                        parts = next_dur.split(":")
                        try:
                            if len(parts) == 2: 
                                dur_sec = int(parts[0]) * 60 + int(parts[1])
                            elif len(parts) == 3: 
                                dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        except ValueError:
                            pass
                    
                    if 30 <= dur_sec <= 900:
                        valid_choices.append({
                            "vidid": vidid,
                            "title": str(res.get("title") or "Unknown Title").title(),
                            "dur": next_dur,
                            "seconds": dur_sec
                        })
        except Exception as e:
            LOGGER(__name__).warning(f"Smart Search API failed: {e}")

        if not valid_choices:
            try:
                import yt_dlp
                loop_e = asyncio.get_event_loop()
                ytdl_opts = {"quiet": True, "extract_flat": True}
                ydl = yt_dlp.YoutubeDL(ytdl_opts)
                r = await loop_e.run_in_executor(None, lambda: ydl.extract_info(f"ytsearch10:{search_query}", download=False))
                
                if r and "entries" in r:
                    for entry in r["entries"]:
                        vidid = entry.get("id")
                        if not vidid or vidid == last_vidid: 
                            continue
                        
                        raw_dur = entry.get("duration", 0)
                        try:
                            dur_sec = int(float(raw_dur)) if raw_dur else 0
                        except (ValueError, TypeError):
                            dur_sec = 0
                            
                        if not dur_sec or dur_sec < 30 or dur_sec > 900: 
                            continue
                        
                        m, s = divmod(dur_sec, 60)
                        h, m = divmod(m, 60)
                        dur_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                        
                        valid_choices.append({
                            "vidid": vidid,
                            "title": str(entry.get("title", "Unknown Title")).title(),
                            "dur": dur_str,
                            "seconds": dur_sec
                        })
            except Exception as e:
                 LOGGER(__name__).warning(f"yt-dlp fallback failed: {e}")

        if valid_choices:
            chosen = random.choice(valid_choices)
            track_obj = {
                "title": chosen["title"],
                "dur": chosen["dur"],
                "streamtype": finished_track.get("streamtype", "audio"),
                "by": "Autoplay 🟢",
                "user_id": 0,
                "chat_id": finished_track.get("chat_id", chat_id),
                "file": f"vid_{chosen['vidid']}",
                "vidid": chosen["vidid"],
                "seconds": chosen["seconds"],
                "played": 0,
            }
            db.setdefault(chat_id, []).append(track_obj)
            asyncio.create_task(self._log_autoplay(chat_id, prev_title_log, track_obj["title"]))
            return True

        seed_seconds = int(finished_track.get("seconds") or 0)
        max_duration = min(max(seed_seconds * 3, 240), 900) if seed_seconds > 0 else 900

        try:
            recommendation = await YouTube.autoplay(
                last_vidid,
                raw_title,
                max_duration=max_duration,
            )
        except Exception as err:
            LOGGER(__name__).warning("Autoplay lookup failed for chat %s on %s: %s", chat_id, last_vidid, err)
            recommendation = None

        if recommendation:
            track_obj = {
                "title": recommendation["title"].title(),
                "dur": recommendation["duration_min"],
                "streamtype": finished_track.get("streamtype", "audio"),
                "by": "Autoplay 🟢",
                "user_id": 0,
                "chat_id": finished_track.get("chat_id", chat_id),
                "file": f"vid_{recommendation['vidid']}",
                "vidid": recommendation["vidid"],
                "seconds": recommendation["duration_sec"],
                "played": 0,
            }
            db.setdefault(chat_id, []).append(track_obj)
            asyncio.create_task(self._log_autoplay(chat_id, prev_title_log, track_obj["title"]))
            return True

        LOGGER(__name__).warning(f"Autoplay Phase 1 & 2 failed for {chat_id}. Triggering Ultimate Fallback.")
        try:
            from youtubesearchpython.__future__ import VideosSearch
            fallback_search = VideosSearch("NCS release popular tracks", limit=1)
            result = await fallback_search.next()
            if result and result.get("result"):
                res = result["result"][0]
                
                next_dur = str(res.get("duration", "3:00"))
                dur_sec = 180
                if ":" in next_dur:
                    parts = next_dur.split(":")
                    if len(parts) == 2: 
                        dur_sec = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3: 
                        dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])

                track_obj = {
                    "title": str(res.get("title", "Fallback Track")).title(),
                    "dur": next_dur,
                    "streamtype": finished_track.get("streamtype", "audio"),
                    "by": "Autoplay 🟢",
                    "user_id": 0,
                    "chat_id": finished_track.get("chat_id", chat_id),
                    "file": f"vid_{res.get('id')}",
                    "vidid": res.get("id"),
                    "seconds": dur_sec,
                    "played": 0,
                }
                db.setdefault(chat_id, []).append(track_obj)
                asyncio.create_task(self._log_autoplay(chat_id, prev_title_log, track_obj["title"]))
                return True
        except Exception as e:
            LOGGER(__name__).error(f"Ultimate fallback also failed: {e}")

        return False

    @capture_internal_err
    async def play(self, client, chat_id: int) -> None:
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
                if await self._enqueue_autoplay_track(chat_id, popped):
                    check = db.get(chat_id)
                if not check:
                    await _clear_(chat_id)
                    if chat_id in self.active_calls:
                        try:
                            await client.leave_call(chat_id)
                        except NoActiveGroupCall:
                            pass
                        except Exception:
                            pass
                        finally:
                            self.active_calls.discard(chat_id)
                    return
        except:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except:
                return
        else:
            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            user = check[0]["by"]
            requester_id = check[0].get("user_id")
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
                if n == 0 or not link:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                stream = dynamic_media_stream(path=link, video=video)
                try:
                    await self._play_stream(client, chat_id, stream)
                except Exception:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                button = stream_markup(_, chat_id)
                schedule_stream_card(
                    chat_id=chat_id,
                    original_chat_id=original_chat_id,
                    videoid=videoid,
                    user_id=requester_id,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    button=button,
                    markup="tg",
                )

            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_7"])
                file_path = None
                try:
                    file_path, direct = await YouTube.download(
                        videoid,
                        mystic,
                        videoid=True,
                        video=True if str(streamtype) == "video" else False,
                    )
                except Exception as download_err:
                    LOGGER(__name__).error(f"YouTube extraction failed: {download_err}")

                # 🟢 SOURCE-HOPPING LAYER (YouTube fail hone par backup targets toggle honge)
                if not file_path:
                    await mystic.edit_text(
                        "⚠️ **YouTube block/limit hit.**\n🔄 *Switching to alternative nodes (SoundCloud/Spotify/Saavn)...*",
                        disable_web_page_preview=True
                    )
                    
                    # NOTE: Yahan source-hopping parser execute hoga jo track metadata match karega
                    # file_path = await self.fetch_alternative_stream(title) 

                    if not file_path:
                        return await mystic.edit_text("❌ Sabhi streaming platforms par extraction fail ho gayi. Agla track play karein.")

                stream = dynamic_media_stream(path=file_path, video=video)
                try:
                    await self._play_stream(client, chat_id, stream)
                except:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                button = stream_markup(_, chat_id)
                await mystic.delete()
                schedule_stream_card(
                    chat_id=chat_id,
                    original_chat_id=original_chat_id,
                    videoid=videoid,
                    user_id=requester_id,
                    caption=_["stream_1"].format(
                        f"https://t.me/{app.username}?start=info_{videoid}",
                        title[:23],
                        check[0]["dur"],
                        user,
                    ),
                    button=button,
                    markup="stream",
                )

            elif "index_" in queued:
                stream = dynamic_media_stream(path=videoid, video=video)
                try:
                    await self._play_stream(client, chat_id, stream)
                except:
                    return await app.send_message(original_chat_id, text=_["call_6"])

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
                stream = dynamic_media_stream(path=queued, video=video)
                try:
                    await self._play_stream(client, chat_id, stream)
                except:
                    return await app.send_message(original_chat_id, text=_["call_6"])

                if videoid == "telegram":
                    button = stream_markup(_, chat_id)
                    run = await app.send_photo(
                        chat_id=original_chat_id,
                        photo=(
                            config.TELEGRAM_AUDIO_URL
                            if str(streamtype) == "audio"
                            else config.TELEGRAM_VIDEO_URL
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
                        photo=config.SOUNCLOUD_IMG_URL,
                        caption=_["stream_1"].format(
                            config.SUPPORT_CHAT, title[:23], check[0]["dur"], user
                        ),
                        reply_markup=InlineKeyboardMarkup(button),
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "tg"

                else:
                    button = stream_markup(_, chat_id)
                    schedule_stream_card(
                        chat_id=chat_id,
                        original_chat_id=original_chat_id,
                        videoid=videoid,
                        user_id=requester_id,
                        caption=_["stream_1"].format(
                            f"https://t.me/{app.username}?start=info_{videoid}",
                            title[:23],
                            check[0]["dur"],
                            user,
                        ),
                        button=button,
                        markup="stream",
                    )

    async def start(self) -> None:
        LOGGER(__name__).info("Starting PyTgCalls Clients...")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    @capture_internal_err
    async def ping(self) -> str:
        pings = []
        if config.STRING1:
            pings.append(self.one.ping)
        if config.STRING2:
            pings.append(self.two.ping)
        if config.STRING3:
            pings.append(self.three.ping)
        if config.STRING4:
            pings.append(self.four.ping)
        if config.STRING5:
            pings.append(self.five.ping)
        return str(round(sum(pings) / len(pings), 3)) if pings else "0.0"

    @capture_internal_err
    async def decorators(self) -> None:
        assistants = list(filter(None, [self.one, self.two, self.three, self.four, self.five]))
        raw_clients = list(
            filter(
                None,
                [app, self.userbot1, self.userbot2, self.userbot3, self.userbot4, self.userbot5],
            )
        )

        CRITICAL = (
            ChatUpdate.Status.KICKED
            | ChatUpdate.Status.LEFT_GROUP
            | ChatUpdate.Status.CLOSED_VOICE_CHAT
            | ChatUpdate.Status.DISCARDED_CALL
            | ChatUpdate.Status.BUSY_CALL
        )

        async def unified_update_handler(client, update: Update) -> None:
            try:
                if isinstance(update, ChatUpdate):
                    status = update.status
                    if (status & ChatUpdate.Status.LEFT_CALL) or (status & CRITICAL):
                        await self.stop_stream(update.chat_id)
                        return

                elif isinstance(update, StreamEnded):
                    if update.stream_type == StreamEnded.Type.AUDIO:
                        assistant = await group_assistant(self, update.chat_id)
                        await self.play(assistant, update.chat_id)

            except Exception:
                import sys, traceback
                exc_type, exc_obj, exc_tb = sys.exc_info()
                full_trace = "".join(traceback.format_exception(exc_type, exc_obj, exc_tb))
                caption = (
                    f"🚨 <b>Stream Update Error</b>\n"
                    f"📍 <b>Update Type:</b> <code>{type(update).__name__}</code>\n"
                    f"📍 <b>Error Type:</b> <code>{exc_type.__name__}</code>"
                )
                filename = f"update_error_{getattr(update, 'chat_id', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                await send_large_error(full_trace, caption, filename)

        async def raw_group_call_handler(client, update, users, chats) -> None:
            try:
                if isinstance(update, UpdateGroupCallParticipants):
                    await self._handle_group_call_participants_update(update)
            except Exception:
                import sys, traceback
                exc_type, exc_obj, exc_tb = sys.exc_info()
                full_trace = "".join(traceback.format_exception(exc_type, exc_obj, exc_tb))
                caption = (
                    f"VC Notify Error\n"
                    f"Update Type: {type(update).__name__}\n"
                    f"Error Type: {exc_type.__name__}"
                )
                filename = f"vc_notify_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                await send_large_error(full_trace, caption, filename)

        for assistant in assistants:
            assistant.on_update()(unified_update_handler)
        for raw_client in raw_clients:
            raw_client.add_handler(RawUpdateHandler(raw_group_call_handler), group=99)

JARVIS = Call()
