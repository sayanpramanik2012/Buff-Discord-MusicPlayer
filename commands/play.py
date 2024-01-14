import discord
from . import join  # Import the join module
from search import youtube  # Import the join and youtube modules
from player import player
from search import youtubeplaylist

async def play_command(ctx, url):
    # Call join_command to join the voice channel
    joined = await join.join_command(ctx)

    # Check if the bot successfully joined the voice channel
    if not joined:
        return

    # Your logic for playing music can go here
    # Example: You can use a music library or API to fetch and play the requested song
    if not 'https://www.youtube.com/playlist?list=' in url:
        audio_url = await youtube.search_youtube(url,ctx)
    else:
        return await youtubeplaylist.handle_youtube_playlist(url, ctx)

    if audio_url:
        await player.enqueue_song(ctx, audio_url)
    else:
        await ctx.send("Failed to get audio URL. Please check the provided query.")