import discord
from . import join  # Import the join module
from search import youtube  # Import the join and youtube modules
from player import player
from search import youtubeplaylist, spotifyplaylist


async def play_command(ctx, url):
    # Call join_command to join the voice channel
    joined = await join.join_command(ctx)

    # Check if the bot successfully joined the voice channel
    if not joined:
        return

    if 'spotify.com/playlist/' in url:
        # return await ctx.reply("I am being updated to handle spotify and its playlist")
        return await spotifyplaylist.get_spotify_playlist_tracks(url,ctx)
    else:
        if 'spotify.com/track/'in url:
            await ctx.send("I cant play single songs from spotify give me song name instead.")

    # Your logic for playing music can go here
    if not 'youtube.com/playlist?list=' in url and not 'spotify.com/playlist/' in url:
        from_playlist=False
        audio_url = await youtube.search_youtube(url,ctx)
    else:
        if 'youtube.com/playlist?list=' in url:
            return await youtubeplaylist.handle_youtube_playlist(url, ctx)

    if audio_url:
        await player.enqueue_song(ctx, audio_url,from_playlist)
    else:
        await ctx.send("Failed to get audio URL. Please check the provided query.")