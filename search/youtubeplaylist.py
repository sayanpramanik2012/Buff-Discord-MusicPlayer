# youtubeplaylist.py

from pytube import Playlist
from player import ytplayer
import logging
from typing import List
from pytubefix import YouTube
from googleapiclient.discovery import build
from config import YOUTUBE_API_KEY
import warnings
from player.queue_manager import queue_manager

# Suppress the file_cache warning
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client<4.0.0')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_playlist_queue(ctx) -> str:
    """Get the current YouTube playlist queue as a formatted string"""
    video_urls = queue_manager.get_youtube_playlist_queue(ctx.guild.id)
    
    if not video_urls:
        return "No tracks in the YouTube playlist queue."
    
    queue_list = []
    for i, url in enumerate(video_urls, 1):
        try:
            yt = YouTube(url)
            title = yt.title
            queue_list.append(f"{i}. {title}")
        except Exception as e:
            logger.error(f"Error getting video title for {url}: {e}")
            queue_list.append(f"{i}. {url}")
    
    return "\n".join(queue_list)


async def process_next_track(ctx):
    """Process the next track in the YouTube playlist queue"""
    # Check if bot is still in voice channel
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        queue_manager.clear_youtube_playlist(ctx.guild.id)
        return
    
    url = queue_manager.pop_youtube_playlist_track(ctx.guild.id)
    if not url:
        return
    
    try:
        await ytplayer.enqueue_song(ctx, url, from_playlist=True)
    except Exception as e:
        logger.error(f"Error processing track {url}: {e}")
        # Try next track
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
            request = youtube.playlistItems().list(
                part='snippet',
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()
            
            for item in response['items']:
                video_id = item['snippet']['resourceId']['videoId']
                video_url = f'https://www.youtube.com/watch?v={video_id}'
                video_urls.append(video_url)
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        
        return video_urls
    
    except Exception as e:
        logger.error(f"Error getting playlist videos with Google API: {e}")
        raise


async def handle_youtube_playlist(query: str, ctx):
    """Handle YouTube playlist with improved error handling"""
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
            await ctx.send("❌ No videos found in the playlist.")
            return
        
        # Store in unified queue manager
        queue_manager.set_youtube_playlist(ctx.guild.id, video_urls)
        await ctx.send(f"🎵 Found **{total_videos}** videos in the playlist. Starting playback...")
        
        # Start processing the first track
        await process_next_track(ctx)
    
    except Exception as e:
        logger.error(f"Error handling YouTube playlist: {e}")
        await ctx.send("❌ Failed to handle the YouTube playlist. Please check the URL and try again.")


async def shuffle_playlist(ctx):
    """Shuffle the current YouTube playlist queue"""
    if len(queue_manager.get_youtube_playlist_queue(ctx.guild.id)) > 0:
        queue_manager.shuffle_youtube_playlist(ctx.guild.id)
        await ctx.send("🔀 YouTube playlist shuffled successfully!")
    else:
        await ctx.send("❌ No YouTube playlist tracks to shuffle.")


def register_voice_events(bot):
    """Register voice state update event handler"""
    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.id == bot.user.id and not after.channel:
            # Bot was disconnected, clear the playlist queue
            queue_manager.clear_youtube_playlist(member.guild.id)
