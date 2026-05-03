"""JSON API endpoints — consumed by the dashboard JS."""

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

import db

api_bp = Blueprint("api", __name__)


@api_bp.route("/status")
def status():
    bot = current_app.bot
    return jsonify({
        "online": bot.is_ready() if bot else False,
        "guilds": len(bot.guilds) if (bot and bot.is_ready()) else 0,
        "users":  sum(g.member_count or 0 for g in bot.guilds) if (bot and bot.is_ready()) else 0,
    })


@api_bp.route("/guild/<guild_id>/plan")
@login_required
def guild_plan(guild_id: str):
    return jsonify({"guild_id": guild_id, "plan": db.get_guild_plan(guild_id)})


@api_bp.route("/guild/<guild_id>/settings", methods=["GET"])
@login_required
def guild_settings_get(guild_id: str):
    return jsonify(db.get_guild_settings(guild_id))


@api_bp.route("/guild/<guild_id>/settings", methods=["POST"])
@login_required
def guild_settings_post(guild_id: str):
    data = request.get_json(force=True, silent=True) or {}
    allowed = {"prefix", "volume", "max_queue_length", "auto_disconnect", "announce_songs"}
    kwargs  = {k: v for k, v in data.items() if k in allowed}
    db.update_guild_settings(guild_id, **kwargs)
    return jsonify({"ok": True, "settings": db.get_guild_settings(guild_id)})


@api_bp.route("/me")
@login_required
def me():
    sub = db.get_subscription(current_user.id)
    return jsonify({
        "id":       current_user.id,
        "username": current_user.username,
        "avatar":   current_user.avatar_url,
        "plan":     sub.get("plan", "free"),
        "is_admin": current_user.is_admin,
    })


# legacy route kept for the old dashboard template
@api_bp.route("/songs")
def songs():
    return jsonify({"songs": [], "total_files": 0, "total_pages": 0})
