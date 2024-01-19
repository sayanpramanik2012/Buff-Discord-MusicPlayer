import spotipy
import asyncio
from spotipy.oauth2 import SpotifyClientCredentials
from . import youtube
from player import player
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

CLIENT_ID = SPOTIFY_CLIENT_ID
CLIENT_SECRET = SPOTIFY_CLIENT_SECRET

async def get_spotify_playlist_tracks(playlist_url, ctx):
    try:
        sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET))

        # Extract playlist ID from the URL
        playlist_id = playlist_url.split('/')[-1].split('?')[0]

        # Get tracks from the Spotify playlist
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']

        # Extract track names and artists
        track_info = [(track['track']['name'], track['track']['artists'][0]['name']) for track in tracks]
        await ctx.send(f"I am adding Songs to queue please wait until next update")

        for name, artist in track_info:
            # Construct a query to search for the song on YouTube
            query = f"{name} {artist} official audio"
            
            try:
                video_url = await youtube.search_youtube(query, ctx)
                await player.enqueue_song(ctx, video_url, from_playlist=True)
            except Exception as e:
                print(f"An error occurred during YouTube search: {e}")

            # Add a short delay to avoid blocking the event loop
            await asyncio.sleep(1)

        await ctx.send(f"I have added all songs to queue.")

    except Exception as e:
        print(f"An error occurred: {e}")