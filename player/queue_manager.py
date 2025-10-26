# queue_manager.py
"""
Unified queue management system for all music sources
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional, Dict, Deque, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Track:
    """Represents a music track"""
    url: str
    title: str
    source: str  # 'youtube', 'spotify_track', 'spotify_playlist', 'youtube_playlist'
    requester_id: int
    artist: Optional[str] = None
    
    def __str__(self):
        if self.artist:
            return f"{self.title} - {self.artist}"
        return self.title


class QueueManager:
    """Centralized queue management for all guilds and track types"""
    
    def __init__(self):
        # Regular song queues (immediate playback)
        self.song_queues: Dict[int, Deque[Track]] = {}
        
        # Playlist queues (background processing)
        self.spotify_playlist_queues: Dict[int, List[Dict[str, str]]] = {}
        self.youtube_playlist_queues: Dict[int, List[str]] = {}
        
        self.logger = logging.getLogger(__name__)
    
    # ===== Song Queue Management =====
    
    def get_song_queue(self, guild_id: int) -> Deque[Track]:
        """Get or create song queue for a guild"""
        if guild_id not in self.song_queues:
            self.song_queues[guild_id] = deque()
        return self.song_queues[guild_id]
    
    def add_track(self, guild_id: int, track: Track):
        """Add a track to the song queue"""
        queue = self.get_song_queue(guild_id)
        queue.append(track)
        self.logger.info(f"Added track: {track.title} to guild {guild_id}")
    
    def pop_next_track(self, guild_id: int) -> Optional[Track]:
        """Get and remove the next track from queue"""
        queue = self.get_song_queue(guild_id)
        if queue:
            track = queue.popleft()
            self.logger.info(f"Popped track: {track.title} from guild {guild_id}")
            return track
        return None
    
    def peek_next_track(self, guild_id: int) -> Optional[Track]:
        """View next track without removing it"""
        queue = self.get_song_queue(guild_id)
        return queue[0] if queue else None
    
    def get_queue_length(self, guild_id: int) -> int:
        """Get number of tracks in song queue"""
        return len(self.get_song_queue(guild_id))
    
    def clear_song_queue(self, guild_id: int):
        """Clear the song queue for a guild"""
        if guild_id in self.song_queues:
            del self.song_queues[guild_id]
            self.logger.info(f"Cleared song queue for guild {guild_id}")
    
    def shuffle_song_queue(self, guild_id: int):
        """Shuffle the song queue"""
        if guild_id in self.song_queues and self.song_queues[guild_id]:
            from random import shuffle
            queue_list = list(self.song_queues[guild_id])
            shuffle(queue_list)
            self.song_queues[guild_id] = deque(queue_list)
            self.logger.info(f"Shuffled song queue for guild {guild_id}")
    
    # ===== Spotify Playlist Queue Management =====
    
    def get_spotify_playlist_queue(self, guild_id: int) -> List[Dict[str, str]]:
        """Get Spotify playlist queue for a guild"""
        if guild_id not in self.spotify_playlist_queues:
            self.spotify_playlist_queues[guild_id] = []
        return self.spotify_playlist_queues[guild_id]
    
    def set_spotify_playlist(self, guild_id: int, tracks: List[Dict[str, str]]):
        """Set the entire Spotify playlist queue"""
        self.spotify_playlist_queues[guild_id] = tracks
        self.logger.info(f"Set {len(tracks)} Spotify playlist tracks for guild {guild_id}")
    
    def pop_spotify_playlist_track(self, guild_id: int) -> Optional[Dict[str, str]]:
        """Get and remove next Spotify playlist track"""
        queue = self.get_spotify_playlist_queue(guild_id)
        if queue:
            return queue.pop(0)
        return None
    
    def clear_spotify_playlist(self, guild_id: int):
        """Clear Spotify playlist queue"""
        if guild_id in self.spotify_playlist_queues:
            del self.spotify_playlist_queues[guild_id]
            self.logger.info(f"Cleared Spotify playlist queue for guild {guild_id}")
    
    def shuffle_spotify_playlist(self, guild_id: int):
        """Shuffle Spotify playlist queue"""
        if guild_id in self.spotify_playlist_queues and self.spotify_playlist_queues[guild_id]:
            from random import shuffle
            shuffle(self.spotify_playlist_queues[guild_id])
            self.logger.info(f"Shuffled Spotify playlist for guild {guild_id}")
    
    # ===== YouTube Playlist Queue Management =====
    
    def get_youtube_playlist_queue(self, guild_id: int) -> List[str]:
        """Get YouTube playlist queue for a guild"""
        if guild_id not in self.youtube_playlist_queues:
            self.youtube_playlist_queues[guild_id] = []
        return self.youtube_playlist_queues[guild_id]
    
    def set_youtube_playlist(self, guild_id: int, video_urls: List[str]):
        """Set the entire YouTube playlist queue"""
        self.youtube_playlist_queues[guild_id] = video_urls
        self.logger.info(f"Set {len(video_urls)} YouTube playlist tracks for guild {guild_id}")
    
    def pop_youtube_playlist_track(self, guild_id: int) -> Optional[str]:
        """Get and remove next YouTube playlist track"""
        queue = self.get_youtube_playlist_queue(guild_id)
        if queue:
            return queue.pop(0)
        return None
    
    def clear_youtube_playlist(self, guild_id: int):
        """Clear YouTube playlist queue"""
        if guild_id in self.youtube_playlist_queues:
            del self.youtube_playlist_queues[guild_id]
            self.logger.info(f"Cleared YouTube playlist queue for guild {guild_id}")
    
    def shuffle_youtube_playlist(self, guild_id: int):
        """Shuffle YouTube playlist queue"""
        if guild_id in self.youtube_playlist_queues and self.youtube_playlist_queues[guild_id]:
            from random import shuffle
            shuffle(self.youtube_playlist_queues[guild_id])
            self.logger.info(f"Shuffled YouTube playlist for guild {guild_id}")
    
    # ===== Global Queue Management =====
    
    def clear_all_queues(self, guild_id: int):
        """Clear all queues for a guild"""
        self.clear_song_queue(guild_id)
        self.clear_spotify_playlist(guild_id)
        self.clear_youtube_playlist(guild_id)
        self.logger.info(f"Cleared all queues for guild {guild_id}")
    
    def has_any_tracks(self, guild_id: int) -> bool:
        """Check if guild has any tracks in any queue"""
        return (
            self.get_queue_length(guild_id) > 0 or
            len(self.get_spotify_playlist_queue(guild_id)) > 0 or
            len(self.get_youtube_playlist_queue(guild_id)) > 0
        )
    
    def get_queue_summary(self, guild_id: int) -> str:
        """Get a summary of all queues for display"""
        song_count = self.get_queue_length(guild_id)
        spotify_count = len(self.get_spotify_playlist_queue(guild_id))
        youtube_count = len(self.get_youtube_playlist_queue(guild_id))
        
        summary = []
        if song_count > 0:
            summary.append(f"Song Queue: {song_count} tracks")
        if spotify_count > 0:
            summary.append(f"Spotify Playlist: {spotify_count} tracks")
        if youtube_count > 0:
            summary.append(f"YouTube Playlist: {youtube_count} tracks")
        
        return "\n".join(summary) if summary else "No tracks in queue"


# Global queue manager instance
queue_manager = QueueManager()
