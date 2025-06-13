# youtube.py
from pytube import YouTube
from youtube_search import YoutubeSearch
from googleapiclient.discovery import build
from config import YOUTUBE_API_KEY
import logging
import warnings

# Suppress the file_cache warning
warnings.filterwarnings('ignore', message='file_cache is only supported with oauth2client<4.0.0')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def search_youtube(query, ctx):
    try:
        if 'https://www.youtube.com/watch?v=' in query:
            return query
        
        # First try using Google's YouTube Data API
        try:
            if not YOUTUBE_API_KEY:
                logger.warning("YouTube API key is not set. Falling back to youtube-search.")
                raise ValueError("YouTube API key is not set")
                
            logger.info(f"Attempting to search with YouTube API key: {YOUTUBE_API_KEY[:5]}...")
            youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
            
            # Search for videos
            search_response = youtube.search().list(
                q=query,
                part='id',
                maxResults=1,
                type='video'
            ).execute()
            
            # Check if any results are found
            if search_response['items']:
                video_id = search_response['items'][0]['id']['videoId']
                video_url = f'https://www.youtube.com/watch?v={video_id}'
                logger.info(f"Found video using YouTube API: {video_url}")
                return video_url
        except Exception as e:
            logger.warning(f"Google API search failed: {e}")
            # Fall back to youtube-search if Google API fails
        
        # Use YoutubeSearch as fallback
        logger.info("Falling back to youtube-search method")
        results = YoutubeSearch(query, max_results=1).to_dict()

        # Check if any results are found
        if results:
            video_id = results[0]['id']
            video_url = f'https://www.youtube.com/watch?v={video_id}'
            logger.info(f"Found video using youtube-search: {video_url}")
            return video_url
        else:
            logger.warning("No results found with either search method")
            return None

    except Exception as e:
        logger.error(f"Error in search_youtube: {e}")
        return None
