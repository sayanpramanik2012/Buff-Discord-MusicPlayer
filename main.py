# main.py
from tenacity import retry, stop_after_attempt, wait_fixed
import discord
from discord.ext import commands, tasks
import yt_dlp as youtube_dl
from commands import join, pause, play, disconnect, skip, resume
from search import youtube
from player import ytplayer
import os
import asyncio
from threading import Thread
from flask import Flask, render_template, request
import logging
from datetime import datetime
import humanize
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

# Load bot token from config file
from config import TOKEN, PREFIX

# Create intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# Create a bot instance with intents
bot = commands.Bot(command_prefix=PREFIX, intents=intents)
bot.voice_contexts = {}

app = Flask(__name__)

# FIXED: Updated to handle both .webm and .mp3 files
def get_cached_songs(page=1, per_page=20):
    """Get list of downloaded songs from downloads directory with pagination"""
    downloads = []
    downloads_dir = './downloads'
    
    if not os.path.exists(downloads_dir):
        return downloads, 0, 0
    
    try:
        # Get only the files we need for this page
        all_files = []
        for filename in os.listdir(downloads_dir):
            # Allow both .webm and .mp3 files
            if filename.endswith(('.webm', '.mp3')):
                file_path = os.path.join(downloads_dir, filename)
                stat = os.stat(file_path)
                all_files.append({
                    'filename': filename,
                    'size': stat.st_size,
                    'mtime': stat.st_mtime
                })
        
        # Sort files by modification time (newest first)
        all_files.sort(key=lambda x: x['mtime'], reverse=True)
        total_files = len(all_files)
        
        # Calculate pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        current_page_files = all_files[start_idx:end_idx]
        
        # Process only the files for current page
        for file_info in current_page_files:
            filename = file_info['filename']
            video_id, ext = os.path.splitext(filename)
            
            # Try to get video info from cache
            try:
                title = filename
                if ext == '.webm':
                    video_info = ytplayer.get_video_info(video_id)
                    title = video_info.get('title', f'Unknown Title ({video_id})')
            except Exception as e:
                logger.error(f"Error getting video info: {e}")
                title = f'Unknown Title ({video_id})'
            
            song_data = {
                'id': video_id,
                'title': title,
                'size': humanize.naturalsize(file_info['size']),
                'date': datetime.fromtimestamp(file_info['mtime']).strftime('%Y-%m-%d %H:%M:%S'),
                'timestamp': file_info['mtime']
            }
            downloads.append(song_data)
        
        return downloads, total_files, (total_files + per_page - 1) // per_page
    
    except Exception as e:
        logger.error(f"Error loading songs: {e}")
        return [], 0, 0

@app.route('/')
def index():
    try:
        # Get page number from query parameters
        page = int(request.args.get('page', 1))
        per_page = 20
        
        # Check if the bot is connected to Discord
        bot_is_online = bot.is_ready()
        
        # Get totals without loading all songs
        total_files = get_total_songs()
        total_pages = (total_files + per_page - 1) // per_page
        
        # Get total servers and users
        total_servers = len(bot.guilds)
        total_users = sum(guild.member_count for guild in bot.guilds)
        
        return render_template('index.html',
                             bot_is_online=bot_is_online,
                             total_servers=total_servers,
                             total_users=total_users,
                             current_page=page,
                             total_pages=total_pages,
                             total_files=total_files)
    except Exception as e:
        logger.error(f"An error occurred in index route: {e}")
        return render_template('index.html',
                             bot_is_online=False,
                             total_servers=0,
                             total_users=0,
                             current_page=1,
                             total_pages=1,
                             total_files=0)

def run_flask_app():
    app.run(debug=False, host='0.0.0.0')

# FIXED: Now checks for both .webm and .mp3 files
def get_total_songs():
    downloads_dir = './downloads'
    if not os.path.exists(downloads_dir):
        return 0
    try:
        return len([f for f in os.listdir(downloads_dir) if f.endswith(('.webm', '.mp3'))])
    except Exception as e:
        logger.error(f"Error counting songs: {e}")
        return 0

@app.route('/api/songs')
def api_songs():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        downloads, total_files, total_pages = get_cached_songs(page, per_page)
        
        return json.dumps({
            'songs': downloads,
            'total_files': total_files,
            'total_pages': total_pages
        })
    except Exception as e:
        logger.error(f"API error: {e}")
        return json.dumps({
            'songs': [],
            'total_files': 0,
            'total_pages': 0
        })

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def run_bot():
    await bot.start(TOKEN)

@tasks.loop(seconds=10)
async def update_status():
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening, 
            name=f"{len(bot.voice_contexts)} servers"
        )
    )

# Register voice events for playlist handlers
from search.spotifyplaylist import register_voice_events as register_spotify_events
from search.youtubeplaylist import register_voice_events as register_youtube_events

def register_events():
    """Register all event handlers"""
    register_spotify_events(bot)
    register_youtube_events(bot)

# Event listener for when the bot is ready
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name}')
    
    # Start the Flask app in a new thread
    flask_thread = Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    update_status.start()
    register_events()

# Command handling JOIN
@bot.command(name='join', help='Join the voice channel')
async def joinCommand(ctx):
    try:
        bot.voice_contexts[ctx.guild.id] = ctx
        await join.join_command(ctx)
    except Exception as e:
        logger.error(f"Error in join command: {e}")
        await ctx.send("❌ Failed to join voice channel.")

# Command handling PLAY
@bot.command(name='play', aliases=['p'], help='Play a song from YouTube or Spotify')
async def playCommand(ctx, *, query: str = None):
    if not query:
        await ctx.send("❌ Please provide a song name or URL!")
        return
    
    try:
        bot.voice_contexts[ctx.guild.id] = ctx
        await play.play_command(ctx, query)
    except Exception as e:
        logger.error(f"Error in play command: {e}")
        await ctx.send("❌ Failed to play song.")

@bot.command(name='pause', help='Pause the current song')
async def pauseCommand(ctx):
    await pause.pause_command(ctx)

@bot.command(name='resume', help='Resume the paused song')
async def resumeCommand(ctx):
    await resume.resume_command(ctx)

@bot.command(name='skip', aliases=['s', 'next'], help='Skip the current song')
async def skipCommand(ctx):
    await skip.skip_command(ctx)

@bot.command(name='disconnect', aliases=['dc', 'leave'], help='Disconnect from voice channel')
async def disconnectCommand(ctx):
    await disconnect.disconnect_command(ctx)
    bot.voice_contexts.pop(ctx.guild.id, None)

@bot.command(name='stop', help='Stop playback and disconnect')
async def stopCommand(ctx):
    await disconnect.disconnect_command(ctx)
    bot.voice_contexts.pop(ctx.guild.id, None)

@bot.command(name='shuffle', help='Shuffle the queue')
async def shuffle_command(ctx):
    from player.queue_manager import queue_manager
    
    if queue_manager.get_queue_length(ctx.guild.id) > 0:
        await ytplayer.shuffle_queue(ctx)
    else:
        # Check Spotify playlist
        from search.spotifyplaylist import shuffle_playlist
        spotify_tracks = queue_manager.get_spotify_playlist_queue(ctx.guild.id)
        if spotify_tracks:
            await shuffle_playlist(ctx)
        else:
            await ctx.send("❌ No tracks to shuffle.")

@bot.command(name='queue', aliases=['q'], help='Show the current queue')
async def queue_command(ctx):
    """Show the current song queue and playlist queues"""
    from player.queue_manager import queue_manager
    from search.spotifyplaylist import get_playlist_queue as get_spotify_queue
    from search.youtubeplaylist import get_playlist_queue as get_youtube_queue
    
    # Get summary
    summary = queue_manager.get_queue_summary(ctx.guild.id)
    
    if not queue_manager.has_any_tracks(ctx.guild.id):
        await ctx.send("📭 No songs in queue.")
        return
    
    # Build detailed queue message
    message_parts = [f"**📋 Queue Summary:**\n{summary}\n"]
    
    # Show regular queue
    if queue_manager.get_queue_length(ctx.guild.id) > 0:
        message_parts.append("**🎵 Current Song Queue:**")
        queue = queue_manager.get_song_queue(ctx.guild.id)
        for i, track in enumerate(list(queue)[:10], 1):
            message_parts.append(f"{i}. {track.title}")
        if len(queue) > 10:
            message_parts.append(f"... and {len(queue) - 10} more")
    
    # Show Spotify playlist
    try:
        spotify_queue = await get_spotify_queue(ctx)
        if "No tracks" not in spotify_queue:
            message_parts.append(f"\n**Spotify Playlist:**\n{spotify_queue[:500]}...")
    except:
        pass
    
    # Show YouTube playlist
    try:
        youtube_queue = await get_youtube_queue(ctx)
        if "No tracks" not in youtube_queue:
            message_parts.append(f"\n**YouTube Playlist:**\n{youtube_queue[:500]}...")
    except:
        pass
    
    full_message = "\n".join(message_parts)
    
    # Split if too long
    if len(full_message) > 1900:
        parts = [full_message[i:i+1900] for i in range(0, len(full_message), 1900)]
        for i, part in enumerate(parts, 1):
            await ctx.send(f"**Queue (Part {i}/{len(parts)}):**\n{part}")
    else:
        await ctx.send(full_message)

@bot.event
async def on_voice_state_update(member, before, after):
    """Handle voice state updates"""
    if member == bot.user and before.channel is not None and after.channel is None:
        # Bot was disconnected
        guild = before.channel.guild
        guild_id = guild.id
        
        from player.queue_manager import queue_manager
        queue_manager.clear_all_queues(guild_id)
        bot.voice_contexts.pop(guild_id, None)
        
        logger.info(f"Force disconnected from {guild.name}, cleared all queues")

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.critical(f"An error occurred: {e}")
