import discord
from . import join  # Import the join module
from search import youtube  # Import the join and youtube modules
from player import player

async def play_command(ctx, url):
    # Call join_command to join the voice channel
    await join.join_command(ctx)

    # Your logic for playing music can go here
    # Example: You can use a music library or API to fetch and play the requested song
    audio_url = await youtube.search_youtube(url)

    if audio_url:
        await player.enqueue_song(ctx, audio_url)
    else:
        await ctx.send("Failed to get audio URL. Please check the provided query.")