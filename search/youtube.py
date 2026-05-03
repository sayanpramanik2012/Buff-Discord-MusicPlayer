"""
YouTube search and playlist extraction via yt-dlp.
All network I/O runs in a thread-pool executor to avoid blocking the event loop.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import yt_dlp

import config

logger = logging.getLogger(__name__)

# ─── URL patterns ─────────────────────────────────────────────────────────────
_YT_VIDEO_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)"
)
_YT_PLAYLIST_RE = re.compile(
    r"(?:https?://)?(?:www\.)?youtube\.com/playlist\?(?:.*&)?list="
)

# ─── yt-dlp configs ───────────────────────────────────────────────────────────

# tv_embedded and ios clients bypass YouTube's bot-detection challenge more
# reliably than the default web client when running from a server IP.
_EXTRACTOR_ARGS: Dict[str, Any] = {
    "youtube": {"player_client": ["tv_embedded", "ios", "web"]}
}


def _apply_cookies(opts: Dict[str, Any]) -> Dict[str, Any]:
    """Inject cookiefile into opts when YT_COOKIES_FILE is configured."""
    if config.YT_COOKIES_FILE:
        return {**opts, "cookiefile": config.YT_COOKIES_FILE}
    return opts


# For text searches: flat extraction of 5 candidates (fast — no stream URL needed)
_SEARCH_OPTS: Dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": False,          # must be False to get all 5 search entries
    "extract_flat": "in_playlist",
    "source_address": "0.0.0.0",
    "extractor_args": _EXTRACTOR_ARGS,
}

# For direct YouTube URLs: full metadata (title, duration, thumbnail)
_DIRECT_OPTS: Dict[str, Any] = {
    "format": "bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "source_address": "0.0.0.0",
    "extractor_args": _EXTRACTOR_ARGS,
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    },
}

_PLAYLIST_OPTS: Dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "noplaylist": False,
    "source_address": "0.0.0.0",
    "extractor_args": _EXTRACTOR_ARGS,
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _is_short(entry: Dict[str, Any]) -> bool:
    """True if the entry is a YouTube Short or too short to be a real song."""
    url = (
        entry.get("url") or
        entry.get("webpage_url") or
        entry.get("original_url") or
        f"https://www.youtube.com/watch?v={entry.get('id', '')}"
    )
    if "/shorts/" in url:
        return True
    duration = entry.get("duration") or 0
    # Anything under 60 seconds is almost certainly a Short or ad clip
    if 0 < duration < 60:
        return True
    return False


# Keywords that indicate the user already has a specific intent — don't override
_INTENT_KEYWORDS = {"live", "cover", "remix", "acoustic", "karaoke", "lyrics",
                    "instrumental", "official", "audio", "video", "ft.", "feat."}


def _music_query(query: str) -> str:
    """Append 'official audio' to a plain query unless the user already expressed intent."""
    words = set(query.lower().split())
    if words & _INTENT_KEYWORDS:
        return query  # user already specified what they want
    return f"{query} official audio"


# ─── Public helpers ───────────────────────────────────────────────────────────

def is_youtube_url(query: str) -> bool:
    return bool(_YT_VIDEO_RE.search(query))


def is_youtube_playlist_url(query: str) -> bool:
    """True only for pure playlist URLs (not video-with-list-param URLs)."""
    return bool(_YT_PLAYLIST_RE.search(query))


async def search(query: str) -> Optional[Dict[str, Any]]:
    """
    Resolve a search term or YouTube URL to a single yt-dlp info dict.
    For text searches, fetches 5 candidates and skips YouTube Shorts / clips
    under 60 seconds to maximise the chance of returning an actual song.

    Callers should store https://youtube.com/watch?v={info['id']} as the
    permanent track URL — stream URLs inside info expire in ~6 hours.
    """
    loop = asyncio.get_running_loop()

    if is_youtube_url(query):
        # Direct URL — return full info (no filtering; user explicitly chose this)
        def _run_direct() -> Optional[Dict[str, Any]]:
            with yt_dlp.YoutubeDL(_apply_cookies(_DIRECT_OPTS)) as ydl:
                try:
                    return ydl.extract_info(query, download=False)
                except Exception as exc:
                    logger.error("YouTube direct URL error for '%s': %s", query, exc)
                    return None

        return await loop.run_in_executor(None, _run_direct)

    # Text search — fetch 5 candidates, skip Shorts, return first good result
    def _run_search() -> Optional[Dict[str, Any]]:
        with yt_dlp.YoutubeDL(_apply_cookies(_SEARCH_OPTS)) as ydl:
            try:
                info = ydl.extract_info(f"ytsearch5:{_music_query(query)}", download=False)
                if not info or "entries" not in info:
                    return None
                entries = [e for e in info["entries"] if e and e.get("id")]
                if not entries:
                    return None
                # Prefer first non-Short result
                for entry in entries:
                    if not _is_short(entry):
                        return entry
                # All 5 were Shorts — return first anyway as last resort
                logger.warning(
                    "All 5 search results for '%s' were Shorts; returning first", query
                )
                return entries[0]
            except Exception as exc:
                logger.error("YouTube search error for '%s': %s", query, exc)
                return None

    return await loop.run_in_executor(None, _run_search)


async def get_playlist(playlist_url: str) -> List[Dict[str, Any]]:
    """
    Return [{url, title, duration}, ...] for every video in a YouTube playlist.
    Uses extract_flat so it is fast even for large playlists.
    Skips Shorts automatically.
    """
    loop = asyncio.get_running_loop()

    def _run() -> List[Dict[str, Any]]:
        with yt_dlp.YoutubeDL(_apply_cookies(_PLAYLIST_OPTS)) as ydl:
            try:
                info = ydl.extract_info(playlist_url, download=False)
                if not info or "entries" not in info:
                    return []
                results = []
                for e in info["entries"]:
                    if not e or not e.get("id"):
                        continue
                    if _is_short(e):
                        continue
                    results.append({
                        "url": f"https://www.youtube.com/watch?v={e['id']}",
                        "title": e.get("title") or "Unknown",
                        "duration": e.get("duration"),
                    })
                return results
            except Exception as exc:
                logger.error("YouTube playlist error for '%s': %s", playlist_url, exc)
                return []

    return await loop.run_in_executor(None, _run)
