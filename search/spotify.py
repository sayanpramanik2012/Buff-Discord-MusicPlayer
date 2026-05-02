"""
Spotify URL detection and metadata extraction.

The Spotify API only gives us track metadata (title, artist).
Actual audio is always played via YouTube — see commands/music.py for the
Spotify → YouTube search bridge.

The Spotify client is initialised lazily so the module can be imported even
when credentials are not set (the functions just return None/empty list).
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── URL patterns ─────────────────────────────────────────────────────────────
_TRACK_RE    = re.compile(r"spotify(?:\.com/track/|:track:)([A-Za-z0-9]+)")
_PLAYLIST_RE = re.compile(r"spotify(?:\.com/playlist/|:playlist:)([A-Za-z0-9]+)")
_ALBUM_RE    = re.compile(r"spotify(?:\.com/album/|:album:)([A-Za-z0-9]+)")


# ─── Lazy Spotify client ──────────────────────────────────────────────────────

_sp = None


def _client():
    """Return an authenticated spotipy.Spotify instance, or None if unconfigured."""
    global _sp
    if _sp is not None:
        return _sp

    import config
    if not (config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET):
        logger.warning(
            "Spotify credentials not set — Spotify links will not work. "
            "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your .env file."
        )
        return None

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials

        _sp = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(
                client_id=config.SPOTIFY_CLIENT_ID,
                client_secret=config.SPOTIFY_CLIENT_SECRET,
            )
        )
        return _sp
    except Exception as exc:
        logger.error("Failed to initialise Spotify client: %s", exc)
        return None


# ─── URL helpers ──────────────────────────────────────────────────────────────

def is_spotify_url(query: str) -> bool:
    return "open.spotify.com" in query or query.startswith("spotify:")


def detect_type(url: str) -> Optional[str]:
    """Return 'track', 'playlist', 'album', or None."""
    if _TRACK_RE.search(url):
        return "track"
    if _PLAYLIST_RE.search(url):
        return "playlist"
    if _ALBUM_RE.search(url):
        return "album"
    return None


# ─── Metadata fetchers ────────────────────────────────────────────────────────

def get_track_info(url: str) -> Optional[Dict[str, Any]]:
    """
    Return {title, artist, album, duration_ms, search_query} for a Spotify
    track URL, or None on failure.
    """
    sp = _client()
    if not sp:
        return None

    m = _TRACK_RE.search(url)
    if not m:
        return None

    try:
        track = sp.track(m.group(1))
        artist = track["artists"][0]["name"]
        return {
            "title": track["name"],
            "artist": artist,
            "album": track["album"]["name"],
            "duration_ms": track["duration_ms"],
            "search_query": f"{artist} - {track['name']}",
        }
    except Exception as exc:
        logger.error("get_track_info failed: %s", exc)
        return None


def get_playlist_tracks(url: str) -> List[Dict[str, Any]]:
    """
    Return a list of {title, artist, search_query} dicts for every track in a
    Spotify playlist, following pagination automatically.
    """
    sp = _client()
    if not sp:
        return []

    m = _PLAYLIST_RE.search(url)
    if not m:
        return []

    tracks: List[Dict[str, Any]] = []
    try:
        results = sp.playlist_tracks(m.group(1))
        while results:
            for item in results.get("items", []):
                t = item.get("track")
                if t and t.get("name") and t.get("artists"):
                    artist = t["artists"][0]["name"]
                    tracks.append(
                        {
                            "title": t["name"],
                            "artist": artist,
                            "search_query": f"{artist} - {t['name']}",
                            "duration_ms": t.get("duration_ms"),
                        }
                    )
            results = sp.next(results) if results.get("next") else None
    except Exception as exc:
        logger.error("get_playlist_tracks failed: %s", exc)

    return tracks


def get_album_tracks(url: str) -> List[Dict[str, Any]]:
    """
    Return [{title, artist, album, search_query}, ...] for every track in a
    Spotify album, following pagination automatically.
    """
    sp = _client()
    if not sp:
        return []

    m = _ALBUM_RE.search(url)
    if not m:
        return []

    tracks: List[Dict[str, Any]] = []
    try:
        album_info = sp.album(m.group(1))
        album_name = album_info.get("name", "")
        results = sp.album_tracks(m.group(1))
        while results:
            for t in results.get("items", []):
                if t and t.get("name") and t.get("artists"):
                    artist = t["artists"][0]["name"]
                    tracks.append(
                        {
                            "title": t["name"],
                            "artist": artist,
                            "album": album_name,
                            "search_query": f"{artist} - {t['name']}",
                            "duration_ms": t.get("duration_ms"),
                        }
                    )
            results = sp.next(results) if results.get("next") else None
    except Exception as exc:
        logger.error("get_album_tracks failed: %s", exc)

    return tracks
