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

# In main.py - update get_cached_songs function
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
            # FIX: Allow both .webm and .mp3 files
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
                # FIX: Handle different file types
                title = filename
                if ext == '.webm':
                    video_info = ytplayer.get_video_info(video_id)
                    title = video_info.get('title', f'Unknown Title ({video_id})')
                # Add handling for other formats if needed
            except Exception as e:
                print(f"Error getting video info: {e}")
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
        print(f"Error loading songs: {e}")
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
        print(f"An error occurred: {e}")
        return render_template('index.html',
                             bot_is_online=False,
                             total_servers=0,
                             total_users=0,
                             current_page=1,
                             total_pages=1,
                             total_files=0)

def run_flask_app():
    app.run(debug=False,host='0.0.0.0')

def get_total_songs():
    downloads_dir = './downloads'
    if not os.path.exists(downloads_dir):
        return 0
    try:
        return len([f for f in os.listdir(downloads_dir) if f.endswith('.webm')])
    except Exception as e:
        print(f"Error counting songs: {e}")
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
        print(f"API error: {e}")
        return json.dumps({
            'songs': [],
            'total_files': 0,
            'total_pages': 0
        })

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def run_bot():
    await bot.start(TOKEN)

@tasks.loop(seconds=10)  # Update every 10sec
async def update_status():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"{len(bot.voice_contexts)} servers"))

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
    print(f'Logged in as {bot.user.name}')

    # Start the Flask app in a new thread
    flask_thread = Thread(target=run_flask_app)
    flask_thread.start()

    update_status.start()
    register_events()  # Register all event handlers when bot is ready

# Command handling JOIN
@bot.command(name='join', help='Joins the voice channel')
async def joinCommand(ctx):
    try:
        bot.voice_contexts[ctx.guild.id] = ctx
        await join.join_command(ctx)
    except Exception as e:
        await disconnect.disconnect_command(ctx)
        bot.voice_contexts.pop(ctx.guild.id, None)
        bot.voice_contexts[ctx.guild.id] = ctx
        await join.join_command(ctx)

# Command handling PLAY
@bot.command(name='play', help='Used to play songs')
async def playCommand(ctx, *args):
    try:
        bot.voice_contexts[ctx.guild.id] = ctx
        url = ' '.join(args)
        await play.play_command(ctx, url)
    except Exception as e:
        await disconnect.disconnect_command(ctx)
        bot.voice_contexts.pop(ctx.guild.id, None)
        bot.voice_contexts[ctx.guild.id] = ctx
        url = ' '.join(args)
        await play.play_command(ctx, url)

@bot.command(name='disconnect', help='Disconnects the bot from the voice channel')
async def disconnectCommand(ctx):
    await disconnect.disconnect_command(ctx)
    bot.voice_contexts.pop(ctx.guild.id, None)

@bot.command(name='stop', help='Disconnects the bot from the voice channel')
async def disconnectCommand(ctx):
    await disconnect.disconnect_command(ctx)
    bot.voice_contexts.pop(ctx.guild.id, None)

@bot.command(name='pause', help='Pause the bot while playing')
async def pauseCommand(ctx):
    await pause.pause_command(ctx)

@bot.command(name='resume', help='Resume the bot while paused')
async def resumeCommand(ctx):
    await resume.resume_command(ctx)

@bot.command(name='skip')
async def skip_command(ctx):
    """Skip the current song and play the next one"""
    await ytplayer.skip_song(ctx)

@bot.command(name='shuffle', help='Shuffles your queue')
async def shuffle_command(ctx):
    from search.spotifyplaylist import playlist_tracks, shuffle_playlist
    if ctx.guild.id in playlist_tracks and playlist_tracks[ctx.guild.id]:
        await shuffle_playlist(ctx)
    else:
        await ytplayer.shuffle_queue(ctx)

@bot.command(name='queue')
async def queue_command(ctx):
    """Show the current song queue and playlist queues"""
    from search.spotifyplaylist import get_playlist_queue as get_spotify_queue
    from search.youtubeplaylist import get_playlist_queue as get_youtube_queue
    from player import ytplayer
    
    # Get regular queue
    queue_text = ""
    if ctx.guild.id in ytplayer.song_queues and ytplayer.song_queues[ctx.guild.id]:
        queue_text = "**Current Queue:**\n" + "\n".join([f"{i+1}. {url}" for i, url in enumerate(ytplayer.song_queues[ctx.guild.id])])
    else:
        queue_text = "**Current Queue:**\nNo songs in queue."

    # Get Spotify playlist queue with timeout
    try:
        spotify_queue = await asyncio.wait_for(get_spotify_queue(ctx), timeout=5.0)
        spotify_text = f"\n\n**Spotify Playlist Queue:**\n{spotify_queue}"
    except asyncio.TimeoutError:
        spotify_text = "\n\n**Spotify Playlist Queue:**\nError: Timeout while fetching queue"
    except Exception as e:
        # logger.error(f"Error getting Spotify queue: {e}")
        spotify_text = "\n\n**Spotify Playlist Queue:**\nError: Failed to fetch queue"

    # Get YouTube playlist queue with timeout
    try:
        youtube_queue = await asyncio.wait_for(get_youtube_queue(ctx), timeout=5.0)
        youtube_text = f"\n\n**YouTube Playlist Queue:**\n{youtube_queue}"
    except asyncio.TimeoutError:
        youtube_text = "\n\n**YouTube Playlist Queue:**\nError: Timeout while fetching queue"
    except Exception as e:
        # logger.error(f"Error getting YouTube queue: {e}")
        youtube_text = "\n\n**YouTube Playlist Queue:**\nError: Failed to fetch queue"

    # Combine all queues
    full_message = queue_text + spotify_text + youtube_text

    # Split message if it's too long
    if len(full_message) > 1900:
        parts = []
        current_part = ""
        for line in full_message.split('\n'):
            if len(current_part) + len(line) + 1 > 1900:
                parts.append(current_part)
                current_part = line
            else:
                current_part += '\n' + line if current_part else line
        if current_part:
            parts.append(current_part)

        for i, part in enumerate(parts, 1):
            await ctx.send(f"Queue (Part {i}/{len(parts)}):\n{part}")
    else:
        await ctx.send(full_message)

@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and before.channel is not None and after.channel is None:
        guild = before.channel.guild
        guild_id = guild.id

        # Handle the bot being forcibly disconnected
        if guild_id in ytplayer.song_queues:
            voice_channel_client = discord.utils.get(bot.voice_clients, guild=guild.name)

            # Clear the queue for the guild
            del ytplayer.song_queues[guild_id]

            # Optional: Notify users about the disconnection and queue clearance
            text_channels = guild.text_channels
            if text_channels:
                notification_channel = discord.utils.get(text_channels, name=before.channel.name)
                if notification_channel:
                    await notification_channel.send("I have been forcibly disconnected, and I will clear queue too.")
                else:
                    print(f"force disconnected from {guild.name}")

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except Exception as e:
        print(f"An error occurred: {e}")