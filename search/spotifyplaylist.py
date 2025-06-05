import spotipy
import asyncio
from spotipy.oauth2 import SpotifyClientCredentials
from . import youtube
from player import ytplayer
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
import logging
from typing import List, Tuple, Dict
from functools import lru_cache
import discord

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Spotify client
sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

# Store playlist tracks for each guild
playlist_tracks: Dict[int, List[Dict[str, str]]] = {}

@lru_cache(maxsize=100)
def get_playlist_tracks(playlist_id: str) -> List[Tuple[str, str]]:
    """Cache playlist tracks to avoid repeated API calls"""
    results = sp.playlist_tracks(playlist_id)
    return [(track['track']['name'], track['track']['artists'][0]['name']) 
            for track in results['items']]

async def ensure_voice_client(ctx) -> bool:
    """Ensure the bot is in a voice channel and return True if successful"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    
    if not voice_client:
        # Try to join the user's voice channel
        if ctx.author.voice:
            try:
                voice_client = await ctx.author.voice.channel.connect()
                logger.info(f"Joined voice channel: {voice_client.channel.name}")
                return True
            except Exception as e:
                logger.error(f"Failed to join voice channel: {e}")
                return False
        else:
            logger.warning("User is not in a voice channel")
            return False
    
    if not voice_client.is_connected():
        try:
            await voice_client.connect()
            logger.info(f"Reconnected to voice channel: {voice_client.channel.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to reconnect to voice channel: {e}")
            return False
    
    return True

def clear_playlist_queue(guild_id: int):
    """Clear the playlist queue for a specific guild"""
    if guild_id in playlist_tracks:
        playlist_tracks[guild_id] = []

async def get_playlist_queue(ctx) -> str:
    """Get the current playlist queue as a formatted string"""
    if ctx.guild.id not in playlist_tracks or not playlist_tracks[ctx.guild.id]:
        return "No tracks in the playlist queue."

    queue_list = []
    for i, track in enumerate(playlist_tracks[ctx.guild.id], 1):
        queue_list.append(f"{i}. {track['name']} - {track['artist']}")

    return "\n".join(queue_list)

async def process_next_track(ctx):
    """Process the next track in the playlist queue"""
    if ctx.guild.id not in playlist_tracks or not playlist_tracks[ctx.guild.id]:
        return

    # Check if bot is still in voice channel
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        clear_playlist_queue(ctx.guild.id)
        return

    track = playlist_tracks[ctx.guild.id][0]
    try:
        # Search for the track on YouTube
        query = f"{track['name']} {track['artist']} official audio"
        video_url = await youtube.search_youtube(query, ctx)
        
        if video_url:
            await ytplayer.enqueue_song(ctx, video_url, from_playlist=True)
            # Remove the processed track from the queue
            playlist_tracks[ctx.guild.id].pop(0)
        else:
            logger.error(f"Could not find YouTube video for track: {track['name']} - {track['artist']}")
            # Remove the failed track and try the next one
            playlist_tracks[ctx.guild.id].pop(0)
            await process_next_track(ctx)
    except Exception as e:
        logger.error(f"Error processing track {track['name']}: {e}")
        # Remove the failed track and try the next one
        playlist_tracks[ctx.guild.id].pop(0)
        await process_next_track(ctx)

async def get_spotify_playlist_tracks(playlist_url: str, ctx):
    """Get and store Spotify playlist tracks"""
    try:
        # Extract playlist ID from URL
        playlist_id = playlist_url.split('playlist/')[-1].split('?')[0]
        
        # Get playlist tracks
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']
        
        # Store tracks in the playlist queue
        playlist_tracks[ctx.guild.id] = []
        for item in tracks:
            track = item['track']
            if track:  # Some tracks might be None
                track_info = {
                    'name': track['name'],
                    'artist': track['artists'][0]['name'],
                    'url': f"https://open.spotify.com/track/{track['id']}"
                }
                playlist_tracks[ctx.guild.id].append(track_info)
        
        total_tracks = len(playlist_tracks[ctx.guild.id])
        if total_tracks > 0:
            await ctx.send(f"Found {total_tracks} tracks in the playlist. Starting playback...")
            # Start processing the first track
            await process_next_track(ctx)
        else:
            await ctx.send("No tracks found in the playlist.")
            return False
            
    except Exception as e:
        logger.error(f"Error processing Spotify playlist: {e}")
        await ctx.send("Failed to process the Spotify playlist. Please check the URL and try again.")
        return False
    
    return True

async def shuffle_playlist(ctx):
    """Shuffle the current playlist queue"""
    if ctx.guild.id in playlist_tracks and playlist_tracks[ctx.guild.id]:
        from random import shuffle
        shuffle(playlist_tracks[ctx.guild.id])
        await ctx.send("Playlist shuffled successfully!")
    else:
        await ctx.send("No playlist tracks to shuffle.")

def register_voice_events(bot):
    """Register voice state update event handler"""
    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.id == bot.user.id and not after.channel:
            # Bot was disconnected, clear the playlist queue
            clear_playlist_queue(member.guild.id)