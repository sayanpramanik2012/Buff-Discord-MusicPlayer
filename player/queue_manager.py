"""
Per-guild queue manager — stores Track objects in order.
One flat list per guild; no separate Spotify/YouTube sub-queues.
"""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class TrackSource(Enum):
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"


@dataclass
class Track:
    url: str              # permanent YouTube URL or ytsearch1:... query
    title: str
    source: TrackSource
    requester_id: int
    artist: str = ""
    duration: Optional[int] = None    # seconds
    thumbnail: Optional[str] = None

    @property
    def display_title(self) -> str:
        return f"{self.artist} - {self.title}" if self.artist else self.title


class QueueManager:
    def __init__(self):
        self._queues: Dict[int, List[Track]] = {}

    def _q(self, guild_id: int) -> List[Track]:
        if guild_id not in self._queues:
            self._queues[guild_id] = []
        return self._queues[guild_id]

    def add(self, guild_id: int, track: Track) -> None:
        self._q(guild_id).append(track)

    def add_many(self, guild_id: int, tracks: List[Track]) -> None:
        self._q(guild_id).extend(tracks)

    def pop(self, guild_id: int) -> Optional[Track]:
        q = self._q(guild_id)
        return q.pop(0) if q else None

    def peek(self, guild_id: int) -> Optional[Track]:
        q = self._q(guild_id)
        return q[0] if q else None

    def size(self, guild_id: int) -> int:
        return len(self._q(guild_id))

    def is_empty(self, guild_id: int) -> bool:
        return self.size(guild_id) == 0

    def clear(self, guild_id: int) -> None:
        self._queues[guild_id] = []

    def shuffle(self, guild_id: int) -> None:
        random.shuffle(self._q(guild_id))

    def list_tracks(self, guild_id: int) -> List[Track]:
        return list(self._q(guild_id))

    # Legacy alias used by old main.py on_voice_state_update
    def clear_all_queues(self, guild_id: int) -> None:
        self.clear(guild_id)


queue_manager = QueueManager()
