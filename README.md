# Buff Discord Music Player

Buff Discord Music Player is a bot that allows you to play music in your Discord server from various sources such as YouTube and Spotify. It provides commands for joining a voice channel, playing, pausing, resuming, and skipping tracks.

## Features

- Play music from YouTube and Spotify
- Manage playback with commands
- Support for playlists

## Setup

### Prerequisites

- Docker
- Python 3.9
- A Discord bot token
- Spotify API credentials

### Installation

1. Clone the repository:

```bash
git clone https://github.com/sayanpramanik2012/Buff-Discord-MusicPlayer.git
cd Buff-Discord-MusicPlayer
```

2. Create a config.py file with your credentials:

SPOTIFY_CLIENT_ID = 'your_spotify_client_id'
SPOTIFY_CLIENT_SECRET = 'your_spotify_client_secret'


###Running Locally

1. Install dependencies:

```bash
pip install -r requirements.txt
```
2. Run the bot:
   
```bash
python main.py
```

Usage
Commands
!join - Join the voice channel
!play <url> - Play a song from a URL
!pause - Pause the current song
!resume - Resume the paused song
!skip - Skip the current song
!disconnect - Disconnect the bot from the voice channel
Contributing
Contributions are welcome! Please fork the repository and submit a pull request.

License
This project is licensed under the MIT License - see the LICENSE file for details.
