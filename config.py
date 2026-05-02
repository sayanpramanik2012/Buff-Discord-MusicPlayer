import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
PREFIX = os.getenv("PREFIX", "#")

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is not set. "
        "Copy .env.example to .env and fill in your credentials."
    )
