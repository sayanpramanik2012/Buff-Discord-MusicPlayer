# player.py
from collections import deque
import discord
from pytubefix import YouTube
import asyncio
import yt_dlp as youtube_dl
from random import shuffle
import os
from functools import lru_cache
import logging
from search.spotifyplaylist import playlist_tracks, process_next_track
from commands import disconnect

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
AUDIO_SETTINGS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -ar 48000 -ac 2 -b:a 192k -af "bass=g=2,treble=g=2,volume=1"'
}

YDL_OPTS = {
    'format': 'bestaudio[asr=48000]/bestaudio/best',
    'cookiefile': './cookies.txt',
    'quiet': True,
    'outtmpl': './downloads/%(id)s.%(ext)s',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
    },
    'use_po_token': True,
}

# Global state
song_queues = {}

@lru_cache(maxsize=100)
def get_video_info(video_id):
    """Cache video information to avoid repeated API calls"""
    with youtube_dl.YoutubeDL(YDL_OPTS) as ydl:
        return ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

async def download_audio(audio_url, video_id):
    """Download audio file with error handling"""
    audio_file = f'./downloads/{video_id}.webm'
    
    if os.path.exists(audio_file):
        logger.info(f"Using cached audio file: {audio_file}")
        return audio_file

    try:
        with youtube_dl.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(audio_url, download=True)
            audio_file = f'./downloads/{info["id"]}.webm'
            logger.info(f"Downloaded audio file: {audio_file}")
            return audio_file
    except Exception as e:
        logger.error(f"yt-dlp download failed: {e}")
        raise

async def get_audio_stream(audio_url):
    """Get audio stream URL using pytube as fallback"""
    try:
        yt = YouTube(audio_url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        if not audio_stream:
            raise Exception("No audio streams available.")
        return audio_stream.url
    except Exception as e:
        logger.error(f"pytube fallback failed: {e}")
        raise

async def on_song_end(ctx):
    """Handle song end with consistent queue management"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    
    if not voice_client or not voice_client.is_connected():
        return

    # Check regular queue first
    if ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
        next_song = song_queues[ctx.guild.id][0]  # Don't pop here
        await play_audio(ctx, next_song)
    else:
        # Check Spotify playlist
        from search.spotifyplaylist import playlist_tracks as spotify_tracks
        if ctx.guild.id in spotify_tracks and spotify_tracks[ctx.guild.id]:
            from search.spotifyplaylist import process_next_track as process_spotify_track
            await process_spotify_track(ctx)
        # Check YouTube playlist
        elif hasattr(ctx, 'youtube_playlist_tracks'):
            if ctx.guild.id in ctx.youtube_playlist_tracks and ctx.youtube_playlist_tracks[ctx.guild.id]:
                from search.youtubeplaylist import process_next_track as process_youtube_track
                await process_youtube_track(ctx)
        else:
            # Final fallback if no tracks found
            await ctx.send("Queue is empty. Disconnecting...")
            await disconnect_and_clear_queue(ctx)
            await voice_client.disconnect()

async def play_audio(ctx, audio_url):
    """Play audio with improved error handling and resource management"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        logger.warning("Cannot play audio: Bot is not in voice channel")
        return

    # Extract video ID and get info
    try:
        with youtube_dl.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(audio_url, download=False)
            video_id = info['id']
            title = info.get('title', audio_url)
    except Exception as e:
        logger.error(f"Info extraction failed: {e}")
        await ctx.send(f"Error retrieving video info: {e}")
        return

    # Ensure queue exists and pop current song
    if ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
        current_song = song_queues[ctx.guild.id].popleft()  # Actual pop happens here
        await ctx.send(f"Now playing: **{title}**")

    try:
        # Try downloading with yt-dlp first
        audio_file = await download_audio(audio_url, video_id)
        audio_source = await discord.FFmpegOpusAudio.from_probe(audio_file)
    except Exception as e:
        logger.warning(f"yt-dlp failed, falling back to pytube: {e}")
        try:
            audio_stream_url = await get_audio_stream(audio_url)
            audio_source = discord.FFmpegPCMAudio(audio_stream_url, **AUDIO_SETTINGS)
        except Exception as fallback_error:
            logger.error(f"All audio source methods failed: {fallback_error}")
            await ctx.send("❌ All audio retrieval methods failed")
            return

    try:
        voice_client.play(
            audio_source,
            after=lambda e: asyncio.run_coroutine_threadsafe(
                on_song_end(ctx), ctx.bot.loop
            ) if not e else None
        )
    except Exception as play_error:
        logger.error(f"Playback failed: {play_error}")
        await ctx.send(f"❌ Playback error: {play_error}")

async def enqueue_song(ctx, audio_url, from_playlist=False):
    """Enqueue song with improved state management"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        logger.warning("Cannot enqueue song: Bot is not in voice channel")
        return

    if ctx.guild.id not in song_queues:
        song_queues[ctx.guild.id] = deque()

    song_queues[ctx.guild.id].append(audio_url)
    
    if not from_playlist:
        if voice_client.is_playing() or voice_client.is_paused():
            await ctx.send(f"Added to queue: {audio_url}")
        if voice_client.is_paused():
            await ctx.send("Currently paused. Use `resume` to continue.")

    # Only start playing if nothing is playing
    if not voice_client.is_playing() and not voice_client.is_paused():
        await play_audio(ctx, audio_url)

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

async def skip_song(ctx):
    """Skip the current song and play the next one in the queue"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if not voice_client or not voice_client.is_connected():
        await ctx.send("I'm not playing anything right now.")
        return

    # Stop current playback (triggers after callback)
    if voice_client.is_playing():
        voice_client.stop()
    elif voice_client.is_paused():
        voice_client.resume()
        voice_client.stop()