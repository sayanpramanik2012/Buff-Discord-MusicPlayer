# player/ytplayer.py - FINAL WORKING VERSION

import discord
import asyncio
import yt_dlp as youtube_dl
from pytubefix import YouTube
import os
from functools import lru_cache
import logging
from .queue_manager import queue_manager, Track

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants - FIXED: Different options for files vs streams
FFMPEG_OPTIONS_FILE = {
    'options': '-vn'  # For local files - NO before_options
}

FFMPEG_OPTIONS_STREAM = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'  # For streams - WITH before_options
}

YDL_OPTS = {
    'format': 'bestaudio/best',
    'cookiefile': './cookies.txt',
    'quiet': True,
    'no_warnings': True,
    'outtmpl': './downloads/%(id)s.%(ext)s',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'opus',
        'preferredquality': '192',
    }],
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
    },
}

@lru_cache(maxsize=100)
def get_video_info(video_id):
    """Cache video information to avoid repeated API calls"""
    try:
        with youtube_dl.YoutubeDL(YDL_OPTS) as ydl:
            return ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    except Exception as e:
        logger.error(f"Error getting video info: {e}")
        return None


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


def check_queue(error, ctx, bot_loop):
    """Synchronous callback for when audio finishes"""
    if error:
        logger.error(f"Playback error in callback: {error}")
    
    # Schedule the async function in the bot's event loop
    coro = play_next_in_queue(ctx)
    fut = asyncio.run_coroutine_threadsafe(coro, bot_loop)
    try:
        fut.result()
    except Exception as e:
        logger.error(f"Error in check_queue: {e}")


async def play_next_in_queue(ctx):
    """Play the next song in queue"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    
    if not voice_client or not voice_client.is_connected():
        return
    
    # Priority 1: Check regular song queue
    if queue_manager.get_queue_length(ctx.guild.id) > 0:
        next_track = queue_manager.peek_next_track(ctx.guild.id)
        if next_track:
            await play_audio(ctx, next_track.url)
            return
    
    # Priority 2: Check Spotify playlist queue
    spotify_tracks = queue_manager.get_spotify_playlist_queue(ctx.guild.id)
    if spotify_tracks:
        try:
            from search.spotifyplaylist import process_next_track as process_spotify
            await process_spotify(ctx)
            return
        except Exception as e:
            logger.error(f"Error processing Spotify playlist: {e}")
    
    # Priority 3: Check YouTube playlist queue
    youtube_tracks = queue_manager.get_youtube_playlist_queue(ctx.guild.id)
    if youtube_tracks:
        try:
            from search.youtubeplaylist import process_next_track as process_youtube
            await process_youtube(ctx)
            return
        except Exception as e:
            logger.error(f"Error processing YouTube playlist: {e}")
    
    # No more tracks - disconnect
    await ctx.send("🔇 Queue is empty. Disconnecting...")
    await disconnect_and_clear_queue(ctx)


async def play_audio(ctx, audio_url):
    """Play audio with improved error handling"""
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
        await ctx.send(f"❌ Error retrieving video info")
        await play_next_in_queue(ctx)
        return
    
    await ctx.send(f"🎵 Now playing: **{title}**")
    
    # Try to get audio source
    audio_source = None
    is_file = False  # Track if we're using a file or stream
    
    try:
        # Try downloading with yt-dlp first
        audio_file = await download_audio(audio_url, video_id)
        # FIXED: Use FFMPEG_OPTIONS_FILE for local files (no before_options)
        audio_source = discord.FFmpegOpusAudio(audio_file, **FFMPEG_OPTIONS_FILE)
        is_file = True
        logger.info(f"Created audio source from file: {audio_file}")
        
    except Exception as e:
        logger.warning(f"yt-dlp failed, falling back to pytube stream: {e}")
        try:
            audio_stream_url = await get_audio_stream(audio_url)
            # FIXED: Use FFMPEG_OPTIONS_STREAM for streams (with before_options)
            audio_source = discord.FFmpegOpusAudio(audio_stream_url, **FFMPEG_OPTIONS_STREAM)
            is_file = False
            logger.info(f"Created audio source from stream")
        except Exception as fallback_error:
            logger.error(f"All audio source methods failed: {fallback_error}")
            await ctx.send("❌ Failed to get audio source. Skipping...")
            await play_next_in_queue(ctx)
            return
    
    # Pop from queue AFTER creating audio source successfully
    if queue_manager.get_queue_length(ctx.guild.id) > 0:
        popped_track = queue_manager.pop_next_track(ctx.guild.id)
        logger.info(f"Playing track: {popped_track.title}")
    
    # Play with callback
    try:
        voice_client.play(
            audio_source,
            after=lambda e: check_queue(e, ctx, ctx.bot.loop)
        )
        logger.info(f"Started playback for: {title} (source: {'file' if is_file else 'stream'})")
    except Exception as play_error:
        logger.error(f"voice_client.play() failed: {play_error}")
        await ctx.send(f"❌ Playback error")
        await play_next_in_queue(ctx)


async def enqueue_song(ctx, audio_url, from_playlist=False):
    """Enqueue song using unified queue manager"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    
    if not voice_client or not voice_client.is_connected():
        logger.warning("Cannot enqueue song: Bot is not in voice channel")
        return
    
    # Create track object
    try:
        with youtube_dl.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(audio_url, download=False)
            title = info.get('title', 'Unknown')
    except:
        title = audio_url
    
    track = Track(
        url=audio_url,
        title=title,
        source='youtube',
        requester_id=ctx.author.id
    )
    
    # Add to queue
    queue_manager.add_track(ctx.guild.id, track)
    
    # Notify user if not from playlist
    if not from_playlist:
        if voice_client.is_playing() or voice_client.is_paused():
            position = queue_manager.get_queue_length(ctx.guild.id)
            await ctx.send(f"✅ Added to queue (Position: {position}): **{title}**")
            if voice_client.is_paused():
                await ctx.send("⏸️ Currently paused. Use `=resume` to continue.")
    
    # Start playing if nothing is playing
    if not voice_client.is_playing() and not voice_client.is_paused():
        await play_audio(ctx, audio_url)


async def disconnect_and_clear_queue(ctx):
    """Disconnect and clear all queues"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    
    if voice_client and voice_client.is_connected():
        await voice_client.disconnect()
    
    queue_manager.clear_all_queues(ctx.guild.id)
    logger.info(f"Disconnected and cleared all queues for Guild ID: {ctx.guild.id}")


async def shuffle_queue(ctx):
    """Shuffle the song queue"""
    if queue_manager.get_queue_length(ctx.guild.id) > 0:
        queue_manager.shuffle_song_queue(ctx.guild.id)
        await ctx.send("🔀 Queue shuffled successfully!")
    else:
        await ctx.send("❌ No songs in the queue to shuffle.")


async def skip_song(ctx):
    """Skip the current song"""
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    
    if not voice_client or not voice_client.is_connected():
        await ctx.send("❌ I'm not playing anything right now.")
        return
    
    if voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏭️ Skipped!")
    elif voice_client.is_paused():
        voice_client.resume()
        voice_client.stop()
        await ctx.send("⏭️ Skipped!")
    else:
        await ctx.send("❌ Nothing is playing.")
