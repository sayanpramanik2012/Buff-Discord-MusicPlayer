import discord
import asyncio
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy
from random import shuffle
from collections import deque
import logging
from functools import lru_cache
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
AUDIO_SETTINGS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -b:a 128k -af "bass=g=1,treble=g=1,volume=1"'
}

# Initialize Spotify client
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

# Global state
song_queues = {}

@lru_cache(maxsize=100)
def get_track_info(track_id):
    """Cache track information to avoid repeated API calls"""
    return sp.track(track_id)

async def play_audio(ctx, track_url):
    """Play audio with improved error handling and resource management"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if not voice_client:
        await ctx.send("I am not connected to a voice channel.")
        return

    if not voice_client.is_playing() and ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
        track_url = song_queues[ctx.guild.id].popleft()
        track_id = track_url.split('/')[-1]

        try:
            track_info = get_track_info(track_id)
            audio_stream_url = track_info['preview_url']

            if not audio_stream_url:
                await ctx.send("Preview URL not available for this track.")
                return

            voice_client.play(
                discord.FFmpegPCMAudio(audio_stream_url, **AUDIO_SETTINGS),
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    on_song_end(ctx, track_url), ctx.bot.loop
                )
            )

            track_name = track_info['name']
            artist_name = track_info['artists'][0]['name']
            logger.info(f"Playing: {track_name} by {artist_name}")
            await ctx.send(f"Playing: {track_name} by {artist_name}")

        except Exception as e:
            logger.error(f"Error playing track: {e}")
            await ctx.send(f"Error playing track: {e}")
    else:
        await ctx.send("No more songs in the queue." if not voice_client.is_playing() else "I'm already playing music.")

async def on_song_end(ctx, track_url):
    """Handle song end with improved state management"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    
    if not voice_client:
        return

    if ctx.message.content.startswith("#skip"):
        voice_client.stop()
        return

    if not ctx.message.content.startswith("#skip"):
        if ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
            if not ctx.message.content.startswith("#disconnect"):
                if len(voice_client.channel.members) > 1:
                    await play_audio(ctx, track_url)
                else:
                    await ctx.send("No one is in the voice channel. Disconnecting...")
                    await disconnect_and_clear_queue(ctx)
                    await voice_client.disconnect()
        else:
            await ctx.send("Queue is empty. Disconnecting...")
            await disconnect_and_clear_queue(ctx)
            await voice_client.disconnect()

async def enqueue_song(ctx, track_url):
    """Enqueue song with improved state management"""
    if ctx.guild.id not in song_queues:
        song_queues[ctx.guild.id] = deque()

    song_queues[ctx.guild.id].append(track_url)
    
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if voice_client.is_playing() or voice_client.is_paused():
        await ctx.send(f"Added to queue: {track_url}")
    if voice_client.is_paused():
        await ctx.send("Currently paused. Use `resume` to continue.")

    if (len(song_queues[ctx.guild.id]) == 1 and 
        not voice_client.is_playing() and 
        not voice_client.is_paused()):
        await play_audio(ctx, track_url)

async def disconnect_and_clear_queue(ctx):
    """Disconnect and clear queue with improved cleanup"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
    if ctx.guild.id in song_queues:
        del song_queues[ctx.guild.id]
    logger.info(f"Disconnected and cleared queue for Guild ID: {ctx.guild.id}")

async def shuffle_queue(ctx):
    """Shuffle queue with improved error handling"""
    if ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
        queue = list(song_queues[ctx.guild.id])
        shuffle(queue)
        song_queues[ctx.guild.id] = deque(queue)
        await ctx.send("Queue shuffled successfully!")
    else:
        await ctx.send("No songs in the queue to shuffle.")
