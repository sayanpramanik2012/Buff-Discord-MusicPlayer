# youtubeplaylist.py
from pytube import Playlist
from player import player

async def handle_youtube_playlist(query, ctx):
    try:
        # Create a Playlist object
        playlist = Playlist(query)
        
        # Extract all video URLs from the playlist
        video_urls = playlist.video_urls
        
        # Enqueue each video URL in the song queue
        for video_url in video_urls:
            await player.enqueue_song(ctx, video_url,from_playlist=True)
            # await print(video_urls)

        await ctx.send(f"All videos from the playlist have been added to the queue.")

    except Exception as e:
        print(f"Error handling YouTube playlist: {e}")
        await ctx.send("Failed to handle the YouTube playlist.")
