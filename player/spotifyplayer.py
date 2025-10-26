# spotifyplaylist.py

import spotipy
import asyncio
from spotipy.oauth2 import SpotifyClientCredentials
from search import youtube
from player import ytplayer
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
import logging
from functools import lru_cache
import discord
from .queue_manager import queue_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Spotify client
sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))


@lru_cache(maxsize=100)
def get_playlist_tracks_cached(playlist_id: str):
    """Cache playlist tracks to avoid repeated API calls"""
    results = sp.playlist_tracks(playlist_id)
    return [(track['track']['name'], track['track']['artists'][0]['name'])
            for track in results['items'] if track['track']]


async def get_playlist_queue(ctx) -> str:
    """Get the current Spotify playlist queue as a formatted string"""
    tracks = queue_manager.get_spotify_playlist_queue(ctx.guild.id)
    
    if not tracks:
        return "No tracks in the Spotify playlist queue."
    
    queue_list = []
    for i, track in enumerate(tracks, 1):
        queue_list.append(f"{i}. {track['name']} - {track['artist']}")
    
    return "\n".join(queue_list)


async def process_next_track(ctx):
    """Process the next track in the Spotify playlist queue"""
    # Check if bot is still in voice channel
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        queue_manager.clear_spotify_playlist(ctx.guild.id)
        return
    
    track = queue_manager.pop_spotify_playlist_track(ctx.guild.id)
    if not track:
        return
    
    try:
        # Search for the track on YouTube
        query = f"{track['name']} {track['artist']} official audio"
        video_url = await youtube.search_youtube(query, ctx)
        
        if video_url:
            await ytplayer.enqueue_song(ctx, video_url, from_playlist=True)
        else:
            logger.error(f"Could not find YouTube video for track: {track['name']} - {track['artist']}")
            # Try next track
            await process_next_track(ctx)
    
    except Exception as e:
        logger.error(f"Error processing track {track['name']}: {e}")
        # Try next track
        await process_next_track(ctx)


async def get_spotify_playlist_tracks(playlist_url: str, ctx):
    """Get and store Spotify playlist tracks"""
    try:
        # Extract playlist ID from URL
        playlist_id = playlist_url.split('playlist/')[-1].split('?')[0]
        
        # Get playlist tracks
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']
        
        # Build track list
        track_list = []
        for item in tracks:
            track = item['track']
            if track:  # Some tracks might be None
                track_info = {
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'url': f"https://open.spotify.com/track/{track['id']}"
                }
                track_list.append(track_info)
        
        if track_list:
            # Store in unified queue manager
            queue_manager.set_spotify_playlist(ctx.guild.id, track_list)
            await ctx.send(f"🎵 Found **{len(track_list)}** tracks in the Spotify playlist. Starting playback...")
            
            # Start processing the first track
            await process_next_track(ctx)
            return True
        else:
            await ctx.send("❌ No tracks found in the playlist.")
            return False
    
    except Exception as e:
        logger.error(f"Error processing Spotify playlist: {e}")
        await ctx.send("❌ Failed to process the Spotify playlist. Please check the URL and try again.")
        return False


async def shuffle_playlist(ctx):
    """Shuffle the current Spotify playlist queue"""
    if len(queue_manager.get_spotify_playlist_queue(ctx.guild.id)) > 0:
        queue_manager.shuffle_spotify_playlist(ctx.guild.id)
        await ctx.send("🔀 Spotify playlist shuffled successfully!")
    else:
        await ctx.send("❌ No Spotify playlist tracks to shuffle.")


def register_voice_events(bot):
    """Register voice state update event handler"""
    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.id == bot.user.id and not after.channel:
            # Bot was disconnected, clear the playlist queue
            queue_manager.clear_spotify_playlist(member.guild.id)
