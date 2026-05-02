"""
Core audio engine.

All audio is streamed directly via yt-dlp + FFmpeg — no local downloads.
Supports ytsearch1:... queries (used for Spotify→YouTube lookup) as well as
direct youtube.com/watch?v=... URLs.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import discord
import yt_dlp

import db
from .queue_manager import Track, TrackSource, queue_manager

logger = logging.getLogger(__name__)

# ─── yt-dlp format strings per plan ──────────────────────────────────────────
# Pro/Max: native Opus passthrough → webm/opus → m4a → any best audio (zero re-encode path)
# Free:    cap at 128 kbps to stay within plan limits
_FMT_PREMIUM = "bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best"
_FMT_FREE    = "bestaudio[abr<=128]/bestaudio/best"

_BASE_YTDL_OPTS: Dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "source_address": "0.0.0.0",
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    },
}


def _ytdl_opts_for_plan(plan: str) -> Dict[str, Any]:
    fmt = _FMT_PREMIUM if plan in ("pro", "max") else _FMT_FREE
    return {**_BASE_YTDL_OPTS, "format": fmt}


# ─── FFmpeg options ───────────────────────────────────────────────────────────
_FFMPEG_BEFORE = (
    "-reconnect 1 "
    "-reconnect_streamed 1 "
    "-reconnect_delay_max 5 "
    "-analyzeduration 0 "
    "-loglevel warning"
)
_FFMPEG_OPTS = "-vn"

# ─── Per-guild state ──────────────────────────────────────────────────────────
_current: Dict[int, Track] = {}


# ─── Public helpers ───────────────────────────────────────────────────────────

def get_current_track(guild_id: int) -> Optional[Track]:
    return _current.get(guild_id)


async def enqueue_and_play(
    voice_client: discord.VoiceClient,
    guild_id: int,
    track: Track,
    text_channel: Optional[discord.abc.Messageable] = None,
) -> None:
    """Add *track* to the guild queue. If idle, start playback immediately."""
    already_playing = voice_client.is_playing() or voice_client.is_paused()
    queue_manager.add(guild_id, track)

    if already_playing:
        pos = queue_manager.size(guild_id)
        if text_channel:
            await text_channel.send(
                f"Added to the queue at position **#{pos}**: {track.display_title} 🎶"
            )
    else:
        await _advance(voice_client, guild_id, text_channel)


async def skip_current(voice_client: discord.VoiceClient) -> bool:
    """Stop the current track; the after-callback will advance the queue."""
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
        return True
    return False


async def stop_all(voice_client: discord.VoiceClient, guild_id: int) -> None:
    """Clear queue, stop playback, and disconnect."""
    queue_manager.clear(guild_id)
    _current.pop(guild_id, None)
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
    if voice_client.is_connected():
        await voice_client.disconnect()


# ─── Internal ─────────────────────────────────────────────────────────────────

async def _advance(
    voice_client: discord.VoiceClient,
    guild_id: int,
    text_channel: Optional[discord.abc.Messageable],
) -> None:
    if not voice_client or not voice_client.is_connected():
        return

    track = queue_manager.pop(guild_id)
    if track is None:
        _current.pop(guild_id, None)
        if text_channel:
            await text_channel.send(
                "That's all the songs in the queue! "
                "It was fun playing for you — see you next time! 👋"
            )
        await voice_client.disconnect()
        return

    await _play_track(voice_client, guild_id, track, text_channel)


async def _fetch_info(url: str, guild_id: int) -> Optional[Dict[str, Any]]:
    """Run yt-dlp in a thread pool using the correct quality tier for this guild."""
    loop = asyncio.get_running_loop()
    plan = db.get_guild_plan(str(guild_id))
    opts = _ytdl_opts_for_plan(plan)

    def _run() -> Optional[Dict[str, Any]]:
        with yt_dlp.YoutubeDL(opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                # ytsearch1: returns a playlist wrapper; unwrap it
                if info and "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    info = entries[0] if entries else None
                return info
            except yt_dlp.utils.DownloadError as exc:
                logger.error("yt-dlp DownloadError for '%s': %s", url, exc)
                return None
            except Exception as exc:
                logger.error("yt-dlp unexpected error for '%s': %s", url, exc)
                return None

    return await loop.run_in_executor(None, _run)


async def _play_track(
    voice_client: discord.VoiceClient,
    guild_id: int,
    track: Track,
    text_channel: Optional[discord.abc.Messageable],
) -> None:
    try:
        info = await _fetch_info(track.url, guild_id)

        if not info:
            logger.warning("No info returned for track: %s", track.display_title)
            if text_channel:
                await text_channel.send(
                    f"Hmm, I couldn't get the stream for **{track.display_title}** — "
                    "not sure what happened there. I'll skip it and move on! ⏭"
                )
            await _advance(voice_client, guild_id, text_channel)
            return

        stream_url = info.get("url")
        if not stream_url:
            formats = info.get("formats", [])
            audio_formats = [
                f for f in formats if f.get("acodec", "none") != "none" and f.get("url")
            ]
            if audio_formats:
                audio_formats.sort(key=lambda f: f.get("abr") or 0, reverse=True)
                stream_url = audio_formats[0]["url"]

        if not stream_url:
            logger.error("No stream URL in yt-dlp response for '%s'", track.display_title)
            if text_channel:
                await text_channel.send(
                    f"Looks like **{track.display_title}** isn't playable right now — "
                    "it might be age-restricted or unavailable in this region. "
                    "I'll skip it and try the next one! ⏭"
                )
            await _advance(voice_client, guild_id, text_channel)
            return

        # Fill metadata gaps from yt-dlp response
        if not track.title or track.title == "Unknown":
            track.title = info.get("title", "Unknown")
        if not track.artist:
            track.artist = info.get("uploader") or info.get("channel") or ""
        if not track.thumbnail:
            track.thumbnail = info.get("thumbnail")
        if not track.duration:
            track.duration = info.get("duration")

        _current[guild_id] = track

        # from_probe auto-detects codec; uses copy for native Opus streams
        audio_source = await discord.FFmpegOpusAudio.from_probe(
            stream_url,
            before_options=_FFMPEG_BEFORE,
            options=_FFMPEG_OPTS,
        )

        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
            await asyncio.sleep(0.15)

        if text_channel:
            await text_channel.send(_now_playing_msg(track, guild_id))

        event_loop = asyncio.get_running_loop()

        def _after(err: Optional[Exception]) -> None:
            if err:
                logger.error("Playback error in guild %s: %s", guild_id, err)
            asyncio.run_coroutine_threadsafe(
                _advance(voice_client, guild_id, text_channel),
                event_loop,
            )

        voice_client.play(audio_source, after=_after)

    except Exception as exc:
        logger.error(
            "Exception in _play_track for '%s': %s", track.display_title, exc, exc_info=True
        )
        if text_channel:
            await text_channel.send(
                f"Oops! Something went wrong while trying to play **{track.display_title}**. "
                f"I'll skip it for now and keep going! (`{exc}`)"
            )
        await _advance(voice_client, guild_id, text_channel)


def _now_playing_msg(track: Track, guild_id: int) -> str:
    dur = _fmt_duration(track.duration)
    q = queue_manager.size(guild_id)
    q_info = f" · {q} more track{'s' if q != 1 else ''} in queue" if q else ""
    icon = "🎧" if track.source == TrackSource.SPOTIFY else "▶️"
    return f"{icon} Now playing: **{track.display_title}**{dur}{q_info}"


def _fmt_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return ""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f" `[{h}:{m:02d}:{s:02d}]`" if h else f" `[{m}:{s:02d}]`"
