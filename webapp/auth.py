"""Discord OAuth2 login / logout."""

import urllib.parse

import requests
from flask import Blueprint, redirect, request, session, url_for, current_app
from flask_login import UserMixin, login_user, logout_user, login_required

import config
import db

auth_bp = Blueprint("auth", __name__)

DISCORD_API   = "https://discord.com/api/v10"
OAUTH_URL     = "https://discord.com/api/oauth2/authorize"
TOKEN_URL     = "https://discord.com/api/oauth2/token"
MANAGE_GUILD  = 1 << 5
ADMINISTRATOR = 1 << 3


# ── User model ────────────────────────────────────────────────────────────────

class User(UserMixin):
    def __init__(self, data: dict):
        self.id            = data["id"]
        self.username      = data["username"]
        self.discriminator = data.get("discriminator", "0")
        self.avatar        = data.get("avatar")
        self.is_admin      = bool(data.get("is_admin", 0))

    @property
    def avatar_url(self) -> str:
        if self.avatar:
            return f"https://cdn.discordapp.com/avatars/{self.id}/{self.avatar}.png?size=128"
        return f"https://cdn.discordapp.com/embed/avatars/{int(self.id) % 5}.png"

    @property
    def display_name(self) -> str:
        return self.username


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.route("/login")
def login():
    if not config.DISCORD_CLIENT_ID:
        return "DISCORD_CLIENT_ID is not set in .env", 500
    params = {
        "client_id":     config.DISCORD_CLIENT_ID,
        "redirect_uri":  config.OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope":         "identify guilds",
    }
    url = OAUTH_URL + "?" + urllib.parse.urlencode(params)
    return redirect(url)


@auth_bp.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return redirect(url_for("main.landing"))

    # Exchange code for access token
    token_resp = requests.post(TOKEN_URL, data={
        "client_id":     config.DISCORD_CLIENT_ID,
        "client_secret": config.DISCORD_CLIENT_SECRET,
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  config.OAUTH_REDIRECT_URI,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})

    if not token_resp.ok:
        return "OAuth2 token exchange failed.", 400

    access_token = token_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # Fetch Discord user info
    user_resp   = requests.get(f"{DISCORD_API}/users/@me", headers=headers)
    guilds_resp = requests.get(f"{DISCORD_API}/users/@me/guilds", headers=headers)

    if not user_resp.ok:
        return "Failed to fetch Discord user.", 400

    u      = user_resp.json()
    guilds = guilds_resp.json() if guilds_resp.ok else []

    # Persist user
    db.upsert_user(
        user_id       = u["id"],
        username      = u["username"],
        discriminator = u.get("discriminator", "0"),
        avatar        = u.get("avatar"),
        admin_ids     = config.ADMIN_USER_IDS,
    )

    # Trim guild objects to the 4 fields we use — Discord responses include
    # many extra fields (features, splash, banner, ...) that bloat the session
    # cookie past the 4KB browser limit, causing silent data loss.
    manageable = [
        {
            "id":          g["id"],
            "name":        g["name"],
            "icon":        g.get("icon"),
            "permissions": str(g.get("permissions", "0")),
        }
        for g in guilds
        if int(g.get("permissions", 0)) & (MANAGE_GUILD | ADMINISTRATOR)
    ]
    session["guilds"]       = manageable
    session["access_token"] = access_token
    # Persist to DB so guild list survives session cookie loss / expiry
    db.cache_user_guilds(u["id"], manageable)

    user_obj = User(db.get_user(u["id"]))
    login_user(user_obj, remember=True)
    return redirect(url_for("main.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("main.landing"))
