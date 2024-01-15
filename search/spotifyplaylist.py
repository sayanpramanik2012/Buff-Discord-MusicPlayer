import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from . import youtube
from player import player

SPOTIFY_CLIENT_ID = '69957d4026444e2fac0be2d5b9e0bdd3'
SPOTIFY_CLIENT_SECRET = 'fcc0b5504fa34352bb3f93e95f3e43d3'

async def get_spotify_playlist_tracks(playlist_url,ctx):
    sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))

    # Extract playlist ID from the URL
    playlist_id = playlist_url.split('/')[-1].split('?')[0]

    # Get tracks from the Spotify playlist
    results = sp.playlist_tracks(playlist_id)
    tracks = results['items']

    # Extract track names and artists
    track_info = [(track['track']['name'], track['track']['artists'][0]['name']) for track in tracks]

    for name, artist in track_info:
        # Construct a query to search for the song on YouTube
        query = f"{name} {artist} official audio"
        print (query)
        video_url= await youtube.search_youtube(query,ctx)
        print (video_url)
        await player.enqueue_song(ctx, video_url,from_playlist=True)
    
    await ctx.send(f"All videos from the playlist have been added to the queue.")
