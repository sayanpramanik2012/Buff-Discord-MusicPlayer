"""
YouTube search and playlist extraction via yt-dlp.
All network I/O runs in a thread-pool executor to avoid blocking the event loop.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import yt_dlp

logger = logging.getLogger(__name__)

# ─── URL patterns ─────────────────────────────────────────────────────────────
_YT_VIDEO_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)"
)
_YT_PLAYLIST_RE = re.compile(
    r"(?:https?://)?(?:www\.)?youtube\.com/playlist\?(?:.*&)?list="
)

# ─── yt-dlp configs ───────────────────────────────────────────────────────────
_SEARCH_OPTS: Dict[str, Any] = {
    "format": "bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
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

_PLAYLIST_OPTS: Dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,   # fast: only fetch IDs/titles, no stream URLs
    "noplaylist": False,
    "source_address": "0.0.0.0",
}


# ─── Public helpers ───────────────────────────────────────────────────────────

def is_youtube_url(query: str) -> bool:
    return bool(_YT_VIDEO_RE.search(query))


def is_youtube_playlist_url(query: str) -> bool:
    """True only for pure playlist URLs (not video-with-list-param URLs)."""
    return bool(_YT_PLAYLIST_RE.search(query))


async def search(query: str) -> Optional[Dict[str, Any]]:
    """
    Resolve a search term or YouTube URL to a single yt-dlp info dict.
    Returns keys including: id, title, uploader/channel, duration, thumbnail.
    Callers should store  https://youtube.com/watch?v={info['id']}  as the
    permanent track URL — stream URLs inside info expire in ~6 hours.
    """
    loop = asyncio.get_running_loop()
    term = query if is_youtube_url(query) else f"ytsearch1:{query}"

    def _run() -> Optional[Dict[str, Any]]:
        with yt_dlp.YoutubeDL(_SEARCH_OPTS) as ydl:
            try:
                info = ydl.extract_info(term, download=False)
                if info and "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    info = entries[0] if entries else None
                return info
            except Exception as exc:
                logger.error("YouTube search error for '%s': %s", query, exc)
                return None

    return await loop.run_in_executor(None, _run)


async def get_playlist(playlist_url: str) -> List[Dict[str, Any]]:
    """
    Return [{url, title, duration}, ...] for every video in a YouTube playlist.
    Uses extract_flat so it is fast even for large playlists.
    """
    loop = asyncio.get_running_loop()

    def _run() -> List[Dict[str, Any]]:
        with yt_dlp.YoutubeDL(_PLAYLIST_OPTS) as ydl:
            try:
                info = ydl.extract_info(playlist_url, download=False)
                if not info or "entries" not in info:
                    return []
                return [
                    {
                        "url": f"https://www.youtube.com/watch?v={e['id']}",
                        "title": e.get("title") or "Unknown",
                        "duration": e.get("duration"),
                    }
                    for e in info["entries"]
                    if e and e.get("id")
                ]
            except Exception as exc:
                logger.error("YouTube playlist error for '%s': %s", playlist_url, exc)
                return []

    return await loop.run_in_executor(None, _run)
