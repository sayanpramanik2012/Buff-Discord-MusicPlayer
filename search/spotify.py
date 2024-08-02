# spotify.py
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET


# Initialize Spotify client
sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))

async def search_spotify(song_name):
    print(song_name)
    try:
        # Search for the song on Spotify
        results = sp.search(q=song_name, type='track', limit=1)
        
        # Check if any results are found
        if results['tracks']['items']:
            track = results['tracks']['items'][0]
            track_url = track['external_urls']['spotify']
            print(track_url)
            return track_url
        else:
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None
