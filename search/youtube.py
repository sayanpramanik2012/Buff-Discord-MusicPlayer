# youtube.py
from pytube import YouTube
from youtube_search import YoutubeSearch  # Install this library with: pip install youtube-search

async def search_youtube(query,ctx):
    try:
        if 'https://www.youtube.com/watch?v=' in query:
            return query
        
        # Use YoutubeSearch to search for videos based on the query
        results = YoutubeSearch(query, max_results=1).to_dict()

        # Check if any results are found
        if results:
            video_id = results[0]['id']
            video_url = f'https://www.youtube.com/watch?v={video_id}'
            return video_url
        else:
            return None

    except Exception as e:
        print(f"Error: {e}")
        return None
