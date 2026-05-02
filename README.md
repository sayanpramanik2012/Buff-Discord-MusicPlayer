# 🎵 Buff Discord Music Player

A self-hosted Discord music bot that streams high-quality audio from **YouTube** and **Spotify** directly into your voice channel — with zero file downloads, a unified queue system, and full support for playlists and albums.

Built with Python 3.11, discord.py 2.x, yt-dlp, and the Spotify Web API.  
Runs on any machine including **Raspberry Pi 4** via Docker.

---

## ✨ Features

- **YouTube** — video URLs, search queries, Shorts, full playlists
- **Spotify** — single tracks, playlists, and albums  
  *(Spotify audio is sourced from YouTube; the Spotify API is used only to look up the artist + title)*
- **Highest quality audio** — `FFmpegOpusAudio.from_probe` auto-detects Opus streams and copies them without re-encoding; non-Opus formats are transcoded at maximum Discord bitrate
- **Direct streaming** — no disk writes; works great on low-memory devices like Raspberry Pi 4
- **Per-guild queue** — unlimited tracks, shuffle, remove by position, auto-advance
- **Auto-disconnect** — leaves the channel automatically after 60 s of being alone
- **Web dashboard** — lightweight Flask UI showing bot status and server stats on port 5000
- **Multi-platform Docker** — single image runs on both `linux/amd64` and `linux/arm64`

---

## 🏗️ Architecture

```
Buff-Discord-MusicPlayer/
├── main.py                  # Bot entry point + Flask web server
├── config.py                # Env-var loader (fails fast if BOT_TOKEN missing)
│
├── commands/
│   └── music.py             # Single discord.py Cog — all commands live here
│
├── player/
│   ├── queue_manager.py     # Per-guild Track queue (thread-safe list)
│   └── ytplayer.py          # Audio engine: yt-dlp → FFmpeg → Discord voice
│
├── search/
│   ├── youtube.py           # YouTube search + playlist extraction (yt-dlp)
│   └── spotify.py           # Spotify metadata lookup (lazy client init)
│
├── templates/
│   └── index.html           # Web dashboard (Jinja2)
│
├── Dockerfile               # python:3.11-slim + ffmpeg + libopus (ARM64 ready)
├── docker-compose.yml       # One-command deployment
└── .env.example             # Template for environment variables
```

### How a Spotify track gets played

```
User: #play https://open.spotify.com/track/…
        │
        ▼
  search/spotify.py          → Spotify Web API → { title, artist }
        │
        ▼
  Track(url="ytsearch1:artist - title", source=SPOTIFY)
        │                      stored in queue — no YouTube call yet
        ▼
  player/ytplayer.py          → yt-dlp resolves "ytsearch1:…" at play time
        │                      → picks bestaudio (opus/webm preferred)
        ▼
  discord.FFmpegOpusAudio.from_probe
        │                      → codec=copy if already Opus (zero re-encode)
        │                      → re-encode otherwise (libopus, max bitrate)
        ▼
  Discord Voice Channel 🔊
```

---

## 🚀 Quick Start

### 1 — Get credentials

| Credential | Where to get it |
|---|---|
| `BOT_TOKEN` | [discord.com/developers/applications](https://discord.com/developers/applications) → New Application → Bot → Reset Token |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → Create app (Redirect URI can be `http://localhost`) |

Spotify credentials are **optional** — YouTube-only usage works without them.

### 2 — Configure environment

```bash
cp .env.example .env
# Open .env and fill in your values
```

```env
BOT_TOKEN=your_discord_bot_token
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
PREFIX=#
FLASK_PORT=5000
```

### 3a — Run with Docker (recommended)

```bash
docker compose up --build
```

The bot starts automatically and restarts on failure (`restart: unless-stopped`).

### 3b — Run locally (Python 3.11+)

```bash
# System dependency: ffmpeg must be installed
# Ubuntu/Debian:  sudo apt install ffmpeg libopus0
# macOS:          brew install ffmpeg opus
# Windows:        winget install ffmpeg   (or download from ffmpeg.org)

pip install -r requirements.txt
python main.py
```

---

## 🍓 Raspberry Pi 4 Deployment

The Docker image is built on `python:3.11-slim` which ships multi-arch including `linux/arm64`.  
All Python dependencies use pure-Python wheels or have ARM64 builds on PyPI.

```bash
# On your Raspberry Pi 4 (Raspberry Pi OS 64-bit recommended)
sudo apt update && sudo apt install docker.io docker-compose-plugin -y
sudo usermod -aG docker $USER   # log out and back in after this

git clone https://github.com/sayanpramanik2012/Buff-Discord-MusicPlayer.git
cd Buff-Discord-MusicPlayer
cp .env.example .env && nano .env   # fill in tokens

docker compose up -d --build
```

Check logs:
```bash
docker compose logs -f
```

**Pi 4 resource usage** (typical):
| Resource | Idle | Playing |
|---|---|---|
| CPU | < 2 % | 8–15 % |
| RAM | ~80 MB | ~110 MB |

---

## 🎮 Commands

All commands use the prefix set in `.env` (default `#`).

| Command | Aliases | Description |
|---|---|---|
| `#play <query>` | `#p` | Play a song or queue a playlist. Accepts YouTube URL, Spotify URL, or any search text. |
| `#pause` | — | Pause the current song. |
| `#resume` | `#r` | Resume a paused song. |
| `#skip` | `#s`, `#next` | Skip the current song. |
| `#nowplaying` | `#np`, `#current` | Show an embed with the current song, duration, and source. |
| `#queue` | `#q` | List the upcoming queue (up to 15 shown). |
| `#shuffle` | — | Shuffle the upcoming queue. |
| `#remove <#>` | — | Remove a track from the queue by its position number. |
| `#disconnect` | `#dc`, `#leave`, `#stop` | Stop playback, clear the queue, and leave. |
| `#join` | `#j` | Join your voice channel (bot joins automatically on `#play`). |

### Supported URL formats

```
# YouTube
https://www.youtube.com/watch?v=dQw4w9WgXcQ
https://youtu.be/dQw4w9WgXcQ
https://www.youtube.com/shorts/…
https://www.youtube.com/playlist?list=…

# Spotify
https://open.spotify.com/track/…
https://open.spotify.com/playlist/…
https://open.spotify.com/album/…
spotify:track:…   (URI format also works)
```

---

## 🔧 Technical Stack

| Component | Library | Why |
|---|---|---|
| Discord bot framework | `discord.py 2.x` | Native async, Cog extension system, `FFmpegOpusAudio` |
| Audio download / search | `yt-dlp` | Actively maintained, handles YouTube bot-detection, all formats |
| Audio encoding | `FFmpeg` (system) + `libopus` | Zero-copy Opus passthrough; hardware-efficient on ARM |
| Spotify metadata | `spotipy` | Official Spotify Web API client |
| Web dashboard | `Flask` | Lightweight, runs in daemon thread alongside the bot |
| Config | `python-dotenv` | `.env` file support for both local dev and Docker |
| Voice encryption | `PyNaCl` | Required by discord.py for voice channel encryption |

### Audio quality details

yt-dlp format selector (in priority order):
```
bestaudio[acodec=opus]    # webm/opus — Discord's native format; copied as-is
bestaudio[ext=webm]       # webm container, any codec
bestaudio[ext=m4a]        # AAC — re-encoded to Opus by FFmpeg
bestaudio                 # any best audio fallback
best                      # last resort
```

FFmpeg is called with `-reconnect 1 -reconnect_streamed 1` so brief network
drops during playback don't kill the stream.

---

## 🌐 Web Dashboard

The Flask server exposes a status dashboard at `http://localhost:5000` (or whatever `FLASK_PORT` is set to).

Routes:
- `GET /` — HTML dashboard with server count, user count, bot online status
- `GET /api/status` — JSON: `{ online, guilds, users }`

---

## 🐛 Troubleshooting

**"BOT_TOKEN is not set"** — Copy `.env.example` to `.env` and fill in the token.

**No sound / immediately disconnects** — Make sure `ffmpeg` is installed on the host (`ffmpeg -version`) and `libopus0` is present.

**Spotify links don't work** — Check that `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` are set in `.env`. The bot logs a warning on startup if they are missing.

**"No results found"** — yt-dlp occasionally gets rate-limited by YouTube. Wait a moment and retry, or use a direct YouTube URL.

**Raspberry Pi 4: ffmpeg not found in Docker** — Make sure you're running the 64-bit (arm64) version of Raspberry Pi OS. The `python:3.11-slim` base image does not support armv7 (32-bit).

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.
