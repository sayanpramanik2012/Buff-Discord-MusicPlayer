import discord
from . import join
from search import youtube, spotify
from player import ytplayer, spotifyplayer
from search import youtubeplaylist, spotifyplaylist

async def play_command(ctx, url):
    joined = await join.join_command(ctx)
    if not joined:
        return

    if 'spotify.com/track/' in url:
        await spotifyplayer.enqueue_song(ctx, url)
    elif 'spotify.com/playlist/' in url:
        await spotifyplaylist.get_spotify_playlist_tracks(url, ctx)
    elif 'youtube.com/playlist?list=' in url:
        await youtubeplaylist.handle_youtube_playlist(url, ctx)
    else:
        ytaudio_url = await youtube.search_youtube(url, ctx)
        if ytaudio_url:
            await ytplayer.enqueue_song(ctx, ytaudio_url, from_playlist=False)
        else:
            await ctx.send("Failed to get audio URL. Please check the provided query.")