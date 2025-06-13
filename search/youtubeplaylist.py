# youtubeplaylist.py
from pytube import Playlist
from player import ytplayer
import asyncio
import logging
from typing import List, Dict
from pytubefix import YouTube
import discord
from googleapiclient.discovery import build
from config import YOUTUBE_API_KEY
import warnings

# Suppress the file_cache warning
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client<4.0.0')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store playlist tracks for each guild
playlist_tracks: Dict[int, List[str]] = {}

def clear_playlist_queue(guild_id: int):
    """Clear the playlist queue for a specific guild"""
    if guild_id in playlist_tracks:
        playlist_tracks[guild_id] = []

async def get_playlist_queue(ctx) -> str:
    """Get the current YouTube playlist queue as a formatted string"""
    if ctx.guild.id not in playlist_tracks or not playlist_tracks[ctx.guild.id]:
        return "No tracks in the playlist queue."

    queue_list = []
    for i, url in enumerate(playlist_tracks[ctx.guild.id], 1):
        try:
            # Set a timeout for getting video info
            yt = YouTube(url)
            title = yt.title
            queue_list.append(f"{i}. {title}")
        except Exception as e:
            logger.error(f"Error getting video title for {url}: {e}")
            # If we can't get the title, just show the URL
            queue_list.append(f"{i}. {url}")

    return "\n".join(queue_list)

async def process_next_track(ctx):
    """Process the next track in the playlist queue"""
    if ctx.guild.id not in playlist_tracks or not playlist_tracks[ctx.guild.id]:
        return

    # Check if bot is still in voice channel
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        clear_playlist_queue(ctx.guild.id)
        return

    url = playlist_tracks[ctx.guild.id][0]
    try:
        await ytplayer.enqueue_song(ctx, url, from_playlist=True)
        # Remove the processed track from the queue
        playlist_tracks[ctx.guild.id].pop(0)
    except Exception as e:
        logger.error(f"Error processing track {url}: {e}")
        # Remove the failed track and try the next one
        playlist_tracks[ctx.guild.id].pop(0)
        await process_next_track(ctx)

async def get_playlist_videos_google_api(playlist_id: str) -> List[str]:
    """Get playlist videos using Google's YouTube API"""
    try:
        if not YOUTUBE_API_KEY:
            logger.warning("YouTube API key not set. Falling back to pytube.")
            raise ValueError("YouTube API key not set")

        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        video_urls = []
        next_page_token = None

        while True:
            # Get playlist items
            request = youtube.playlistItems().list(
                part='snippet',
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()

            # Extract video IDs and create URLs
            for item in response['items']:
                video_id = item['snippet']['resourceId']['videoId']
                video_url = f'https://www.youtube.com/watch?v={video_id}'
                video_urls.append(video_url)

            # Check if there are more pages
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

        return video_urls
    except Exception as e:
        logger.error(f"Error getting playlist videos with Google API: {e}")
        raise

async def handle_youtube_playlist(query: str, ctx):
    """Handle YouTube playlist with improved error handling and batch processing"""
    try:
        # Extract playlist ID from URL
        playlist_id = query.split('list=')[-1].split('&')[0]
        
        try:
            # First try using Google's YouTube API
            logger.info("Attempting to get playlist videos using Google API")
            video_urls = await get_playlist_videos_google_api(playlist_id)
        except Exception as e:
            logger.warning(f"Google API failed, falling back to pytube: {e}")
            # Fall back to pytube
            playlist = Playlist(query)
            video_urls = list(playlist.video_urls)

        total_videos = len(video_urls)
        if total_videos == 0:
            await ctx.send("No videos found in the playlist.")
            return

        # Store the playlist URLs
        playlist_tracks[ctx.guild.id] = video_urls
        
        await ctx.send(f"Found {total_videos} videos in the playlist. Starting playback...")
        
        # Start processing the first track
        await process_next_track(ctx)

    except Exception as e:
        logger.error(f"Error handling YouTube playlist: {e}")
        await ctx.send("Failed to handle the YouTube playlist. Please check the URL and try again.")

async def shuffle_playlist(ctx):
    """Shuffle the current YouTube playlist queue"""
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
