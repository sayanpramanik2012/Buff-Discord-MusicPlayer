# play.py
import discord
from . import join
from search import youtube, spotify
from player import ytplayer
from search import youtubeplaylist, spotifyplaylist
import logging

logger = logging.getLogger(__name__)

async def play_command(ctx, url):
    """Main play command router"""
    # Ensure bot joins voice channel first
    joined = await join.join_command(ctx)
    if not joined:
        return
    
    # Route based on URL type
    if 'spotify.com/track/' in url:
        # FIXED: Single Spotify track - convert to YouTube search
        await handle_spotify_track(ctx, url)
    
    elif 'spotify.com/playlist/' in url:
        # Spotify playlist - convert all tracks to YouTube
        await spotifyplaylist.get_spotify_playlist_tracks(url, ctx)
    
    elif 'youtube.com/playlist?list=' in url or 'youtu.be/playlist?list=' in url:
        # YouTube playlist
        await youtubeplaylist.handle_youtube_playlist(url, ctx)
    
    else:
        # Regular YouTube search or direct link
        ytaudio_url = await youtube.search_youtube(url, ctx)
        if ytaudio_url:
            await ytplayer.enqueue_song(ctx, ytaudio_url, from_playlist=False)
        else:
            await ctx.send("❌ Failed to get audio URL. Please check the provided query.")


async def handle_spotify_track(ctx, track_url):
    """Handle single Spotify track by converting to YouTube"""
    try:
        # Extract track ID from URL
        track_id = track_url.split('track/')[-1].split('?')[0]
        
        # Get track info from Spotify
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
        from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
        
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET
        ))
        
        track_info = sp.track(track_id)
        track_name = track_info['name']
        artist_name = track_info['artists'][0]['name']
        
        # Search for this track on YouTube
        query = f"{track_name} {artist_name} official audio"
        logger.info(f"Converting Spotify track to YouTube: {query}")
        
        ytaudio_url = await youtube.search_youtube(query, ctx)
        if ytaudio_url:
            await ctx.send(f"🎵 Found: **{track_name}** by **{artist_name}**")
            await ytplayer.enqueue_song(ctx, ytaudio_url, from_playlist=False)
        else:
            await ctx.send(f"❌ Could not find **{track_name}** by **{artist_name}** on YouTube")
    
    except Exception as e:
        logger.error(f"Error handling Spotify track: {e}")
        await ctx.send("❌ Failed to process Spotify track. Please try again.")
