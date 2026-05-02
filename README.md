# 🎵 Buff Discord Music Bot

A self-hosted Discord music bot that streams high-quality audio from **YouTube** and **Spotify** directly into your voice channel — with zero file downloads and a full **subscription-based web dashboard** for managing servers, plans, and settings.

Built with Python 3.11, discord.py 2.x, yt-dlp, Flask, and SQLite.  
Runs on any machine including **Raspberry Pi 4** via Docker (ARM64 native).

---

## ✨ What It Does

### Bot
- **YouTube** — video URLs, search queries, Shorts, and full playlists
- **Spotify** — single tracks, playlists, and albums  
  *(Spotify audio is sourced from YouTube; Spotify API is used only to look up artist + title)*
- **Highest audio quality** — `FFmpegOpusAudio.from_probe` auto-detects Opus streams and copies them without re-encoding; non-Opus streams are transcoded via libopus at maximum Discord bitrate
- **Pure streaming, zero downloads** — yt-dlp fetches a temporary CDN URL at play time; nothing is written to disk
- **Per-guild queue** — shuffle, remove by position, auto-advance, auto-disconnect after 60 s alone
- **Friendly messages** — the bot always speaks in first-person conversational tone

### Web Dashboard
- **Discord OAuth2 login** — users sign in with their Discord account
- **Subscription plans** — Free, Pro ($1.99/mo), Max ($3.99/mo) stored in SQLite
- **Per-server settings** — custom prefix, volume, queue length cap, auto-disconnect, announce-songs toggles
- **Server assignment** — Pro allows 2 premium servers, Max allows 10
- **Admin panel** — admins bypass payment; can set any plan and promote other users
- **Live status** — dashboard polls `/api/status` every 30 s to show bot online state

---

## 🏗️ Architecture

```
Buff-Discord-MusicPlayer/
│
├── main.py                  # Entry point — starts bot + Flask in daemon thread
├── config.py                # Env-var loader (fails fast if BOT_TOKEN missing)
├── db.py                    # SQLite helper — WAL mode, per-call connections
│
├── commands/
│   └── music.py             # Single discord.py Cog — all 10 bot commands
│
├── player/
│   ├── queue_manager.py     # Per-guild Track list — TrackSource enum, Track dataclass
│   └── ytplayer.py          # Audio engine: yt-dlp → FFmpeg → Discord voice
│
├── search/
│   ├── youtube.py           # YouTube URL detection + search + playlist extraction
│   └── spotify.py           # Spotify metadata lookup via spotipy (lazy init)
│
├── webapp/
│   ├── __init__.py          # create_app(bot) factory — registers blueprints
│   ├── auth.py              # Discord OAuth2 login/logout, Flask-Login user model
│   ├── views.py             # Dashboard, server settings, plans, admin routes
│   └── api.py               # JSON endpoints: /api/status, /api/guild/:id/*
│
├── static/webapp/
│   ├── style.css            # Dark theme — CSS variables, sidebar, cards, badges
│   └── app.js               # Sidebar toggle, flash dismiss, live status poll
│
├── templates/
│   ├── index.html           # Public landing page
│   └── webapp/
│       ├── base.html        # Base layout (Inter font, CSS/JS includes)
│       ├── landing.html     # Marketing page — hero, stats, features, pricing
│       ├── dashboard.html   # Server grid with bot-present/plan indicators
│       ├── server_settings.html  # Per-server config form (prefix, volume, queue, toggles)
│       ├── plans.html       # Plan cards + server assignment UI
│       ├── admin.html       # Admin panel — stat grid + user table
│       └── _sidebar.html    # Reusable sidebar partial
│
├── Dockerfile               # python:3.11-slim + ffmpeg + libopus (multi-arch)
├── docker-compose.yml       # One-command deployment
└── .env.example             # Template for all environment variables
```

---

## 🔄 How It Works

### Spotify → YouTube bridge

```
User: #play https://open.spotify.com/track/…
         │
         ▼
  search/spotify.py     →  Spotify Web API  →  { title, artist }
         │
         ▼
  Track(url="ytsearch1:artist - title", source=SPOTIFY)
         │                 stored in queue — no YouTube call yet
         ▼
  player/ytplayer.py    →  yt-dlp resolves "ytsearch1:…" at play time
         │                 picks format based on guild plan (see below)
         ▼
  discord.FFmpegOpusAudio.from_probe
         │                 codec=copy  if stream is already Opus  (zero re-encode)
         │                 libopus re-encode otherwise
         ▼
  Discord Voice Channel 🔊
```

### Plan-based audio quality

| Plan | yt-dlp format selector | Result |
|------|------------------------|--------|
| **Free** | `bestaudio[abr<=128]/bestaudio/best` | 128 kbps cap |
| **Pro** | `bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best` | Native Opus passthrough — zero re-encode |
| **Max** | same as Pro | Native Opus passthrough — zero re-encode |

FFmpeg is called with `-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5` so brief network drops during playback don't kill the stream.

### Dynamic prefix

The bot reads the command prefix from SQLite on every message, so each server can have its own prefix set via the dashboard without a restart.

---

## 🚀 Getting Started

### Step 1 — Credentials

| Credential | Where to get it |
|---|---|
| `BOT_TOKEN` | [discord.com/developers/applications](https://discord.com/developers/applications) → New Application → Bot → Reset Token |
| `DISCORD_CLIENT_ID` | Same application → OAuth2 → Client ID |
| `DISCORD_CLIENT_SECRET` | Same application → OAuth2 → Client Secret |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) → Create app |
| `ADMIN_USER_IDS` | Your Discord user ID (Settings → Advanced → Developer Mode → right-click your name → Copy ID) |

**OAuth2 redirect URI** — in your Discord application's OAuth2 settings, add:
```
http://localhost:5000/auth/callback
```
(or your public domain if deploying remotely)

Spotify credentials are **optional** — YouTube-only usage works without them.

---

### Step 2 — Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
# ── Bot ─────────────────────────────────────────────
BOT_TOKEN=your_discord_bot_token
PREFIX=#

# ── Spotify (optional) ───────────────────────────────
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret

# ── Web Dashboard ────────────────────────────────────
FLASK_PORT=5000
SECRET_KEY=generate-with-python-secrets-token-hex-32
DISCORD_CLIENT_ID=your_discord_application_client_id
DISCORD_CLIENT_SECRET=your_discord_oauth2_client_secret
OAUTH_REDIRECT_URI=http://localhost:5000/auth/callback
ADMIN_USER_IDS=your_discord_user_id
```

Generate a `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

### Step 3a — Run with Docker (recommended)

```bash
docker compose up --build
```

- Bot starts, connects to Discord, and begins listening for commands
- Dashboard is available at `http://localhost:5000`
- Restarts automatically on crash (`restart: unless-stopped`)

To run in the background:
```bash
docker compose up -d --build
docker compose logs -f   # stream logs
```

---

### Step 3b — Run locally (Python 3.11+)

**Install system dependencies first:**

```bash
# Ubuntu / Debian / Raspberry Pi OS
sudo apt update && sudo apt install -y ffmpeg libopus0

# macOS
brew install ffmpeg opus

# Windows
winget install ffmpeg        # then download libopus.dll separately
```

**Install Python dependencies and run:**

```bash
pip install -r requirements.txt
python main.py
```

The bot and web dashboard both start from `main.py`. Dashboard runs on port `5000` by default.

---

## 🍓 Raspberry Pi 4 Deployment

The Docker image uses `python:3.11-slim` which is a multi-arch image — the same `docker compose up` command works on both `linux/amd64` and `linux/arm64` with no changes.

```bash
# On your Raspberry Pi 4 (requires 64-bit Raspberry Pi OS)
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER    # log out and back in after this

git clone https://github.com/sayanpramanik2012/Buff-Discord-MusicPlayer.git
cd Buff-Discord-MusicPlayer
cp .env.example .env
nano .env                        # fill in your tokens

docker compose up -d --build
docker compose logs -f
```

**Typical resource usage on Pi 4:**

| State | CPU | RAM |
|-------|-----|-----|
| Idle (bot + dashboard) | < 2% | ~85 MB |
| Playing audio | 8–15% | ~115 MB |

---

## 🎮 Bot Commands

Default prefix is `#` — configurable per-server from the dashboard.

| Command | Aliases | Description |
|---------|---------|-------------|
| `#play <query or URL>` | `#p` | Play a song or queue a playlist. Accepts YouTube URL, Spotify URL, or any search text. |
| `#pause` | — | Pause the current song. |
| `#resume` | `#r` | Resume a paused song. |
| `#skip` | `#s`, `#next` | Skip the current song; plays next in queue. |
| `#nowplaying` | `#np`, `#current` | Embed with current song, duration, source, and thumbnail. |
| `#queue` | `#q` | List the upcoming queue (up to 15 shown). |
| `#shuffle` | — | Randomly shuffle the upcoming queue. |
| `#remove <#>` | — | Remove a track by its position number in the queue. |
| `#disconnect` | `#dc`, `#leave`, `#stop` | Stop playback, clear the queue, and leave the channel. |
| `#join` | `#j` | Join your current voice channel (happens automatically on `#play`). |

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

## 🌐 Web Dashboard

Access at `http://localhost:5000` (or your server's IP/domain).

### Pages

| Route | Description |
|-------|-------------|
| `/` | Public landing page — bot stats, feature list, pricing |
| `/dashboard` | Your servers — bot-present indicator, current plan badge, manage/invite buttons |
| `/servers/<id>` | Per-server settings — prefix, volume, queue length cap, behaviour toggles |
| `/plans` | Subscription plan cards + server assignment UI |
| `/admin` | Admin panel — user table, set plans, grant/revoke admin (admin-only) |
| `/auth/login` | Redirects to Discord OAuth2 |
| `/auth/logout` | Clears session |

### API endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | `{ online, guilds, users }` — public |
| `/api/me` | GET | Current user info + subscription |
| `/api/guild/<id>/plan` | GET | Guild's current plan |
| `/api/guild/<id>/settings` | GET / POST | Guild settings — requires MANAGE_GUILD permission |

### Subscription plans

| Plan | Price | Premium Servers | Queue Cap | Audio Quality |
|------|-------|-----------------|-----------|---------------|
| **Free** | $0 | 0 | 50 tracks | Standard (≤128 kbps) |
| **Pro** | $1.99/mo | 2 | 200 tracks | Highest (Opus passthrough) |
| **Max** | $3.99/mo | 10 | Unlimited | Highest (Opus passthrough) |

Admins bypass all plan restrictions and can set any plan without payment.

---

## 🔧 Technical Stack

| Component | Library | Notes |
|-----------|---------|-------|
| Discord bot framework | `discord.py 2.x` | Cog extension system, `FFmpegOpusAudio.from_probe` |
| Audio streaming | `yt-dlp` | Streaming only (`download=False`); no disk writes |
| Audio encoding | `FFmpeg` + `libopus` | Zero-copy Opus passthrough on Pro/Max plans |
| Spotify metadata | `spotipy` | Lazy client init — no crash if credentials are absent |
| Web framework | `Flask 3.x` | Runs in daemon thread alongside the bot |
| Auth | `Flask-Login` + Discord OAuth2 | Per-session login, secure cookie |
| Database | `SQLite` (WAL mode) | `db.py` — per-call connections for thread safety |
| Config | `python-dotenv` | `.env` file for local dev and Docker |
| Voice encryption | `PyNaCl` | Required by discord.py for voice channels |
| HTTP client | `requests` | OAuth2 token exchange + Discord API calls |

---

## 🐛 Troubleshooting

**"BOT_TOKEN is not set"**  
Copy `.env.example` to `.env` and fill in all required values.

**No sound / bot immediately disconnects**  
Make sure `ffmpeg` is installed (`ffmpeg -version`) and `libopus0` is present on the host, or that the Docker image built successfully with `apt-get install ffmpeg libopus0`.

**Spotify links don't work**  
Check that `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` are set. The bot logs a warning on startup if they are missing.

**Dashboard login doesn't redirect back**  
The `OAUTH_REDIRECT_URI` in `.env` must exactly match one of the redirect URIs registered in your Discord application's OAuth2 settings.

**"No results found"**  
yt-dlp can occasionally be rate-limited by YouTube. Wait a moment and retry, or use a direct YouTube URL.

**Raspberry Pi 4: ffmpeg not found in Docker**  
Make sure you're running the **64-bit** (aarch64) version of Raspberry Pi OS. The `python:3.11-slim` base image does not support 32-bit ARM (armv7).

**Dashboard shows wrong server list**  
The server list comes from Discord's OAuth2 guilds endpoint at login time. Log out and back in to refresh it.

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.
