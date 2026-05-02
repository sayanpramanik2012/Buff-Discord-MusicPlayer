"""Main web routes — landing, dashboard, server settings, plans, admin."""

from flask import (
    Blueprint, abort, current_app, flash,
    redirect, render_template, request, session, url_for,
)
from flask_login import current_user, login_required

import db
import config

main_bp = Blueprint("main", __name__, template_folder="../templates/webapp")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bot_guild_ids():
    """Return a set of guild ID strings the bot is currently in."""
    bot = current_app.bot
    if bot and bot.is_ready():
        return {str(g.id) for g in bot.guilds}
    return set()


def _enrich_guilds(raw_guilds):
    """Add 'bot_present' and 'plan' keys to each guild dict from session."""
    bot_ids = _bot_guild_ids()
    result  = []
    for g in raw_guilds:
        gid  = str(g["id"])
        icon = g.get("icon")
        result.append({
            **g,
            "id":          gid,
            "icon_url":    (
                f"https://cdn.discordapp.com/icons/{gid}/{icon}.png?size=64"
                if icon else None
            ),
            "bot_present": gid in bot_ids,
            "plan":        db.get_guild_plan(gid),
        })
    return result


# ── Public routes ─────────────────────────────────────────────────────────────

@main_bp.route("/")
def landing():
    bot   = current_app.bot
    stats = {
        "guilds": len(bot.guilds) if (bot and bot.is_ready()) else 0,
        "users":  sum(g.member_count or 0 for g in bot.guilds) if (bot and bot.is_ready()) else 0,
    }
    db_stats = db.get_stats()
    return render_template("webapp/landing.html", stats=stats, db_stats=db_stats)


# ── Authenticated routes ──────────────────────────────────────────────────────

@main_bp.route("/dashboard")
@login_required
def dashboard():
    raw_guilds = session.get("guilds", [])
    guilds     = _enrich_guilds(raw_guilds)
    sub        = db.get_subscription(current_user.id)
    assigned   = db.get_user_assigned_guilds(current_user.id)
    assigned_ids = {a["guild_id"] for a in assigned}
    return render_template(
        "webapp/dashboard.html",
        guilds=guilds,
        sub=sub,
        assigned_ids=assigned_ids,
    )


@main_bp.route("/servers/<guild_id>", methods=["GET", "POST"])
@login_required
def server_settings(guild_id: str):
    # Verify user manages this guild
    manageable_ids = {str(g["id"]) for g in session.get("guilds", [])}
    if guild_id not in manageable_ids and not current_user.is_admin:
        abort(403)

    # Find guild metadata from session
    guild_meta = next(
        (g for g in session.get("guilds", []) if str(g["id"]) == guild_id),
        {"id": guild_id, "name": guild_id, "icon": None},
    )

    if request.method == "POST":
        prefix   = request.form.get("prefix", "#").strip() or "#"
        volume   = min(max(int(request.form.get("volume", 100)), 1), 200)
        q_limit  = min(max(int(request.form.get("max_queue_length", 50)), 1), 500)
        auto_dc  = 1 if request.form.get("auto_disconnect") else 0
        announce = 1 if request.form.get("announce_songs") else 0

        icon = guild_meta.get("icon")
        db.update_guild_settings(
            guild_id,
            guild_name       = guild_meta.get("name", ""),
            guild_icon       = (
                f"https://cdn.discordapp.com/icons/{guild_id}/{icon}.png?size=64" if icon else None
            ),
            prefix           = prefix,
            volume           = volume,
            max_queue_length = q_limit,
            auto_disconnect  = auto_dc,
            announce_songs   = announce,
        )
        flash("Settings saved!", "success")
        return redirect(url_for("main.server_settings", guild_id=guild_id))

    settings = db.get_guild_settings(guild_id)
    plan     = db.get_guild_plan(guild_id)
    return render_template(
        "webapp/server_settings.html",
        guild=guild_meta,
        guild_id=guild_id,
        settings=settings,
        plan=plan,
    )


@main_bp.route("/plans")
@login_required
def plans():
    sub      = db.get_subscription(current_user.id)
    guilds   = _enrich_guilds(session.get("guilds", []))
    assigned = db.get_user_assigned_guilds(current_user.id)
    assigned_map = {a["guild_id"]: a["plan"] for a in assigned}
    return render_template(
        "webapp/plans.html",
        sub=sub,
        guilds=guilds,
        assigned_map=assigned_map,
        limits=db.PLAN_SERVER_LIMITS,
    )


@main_bp.route("/plans/assign", methods=["POST"])
@login_required
def assign_plan():
    guild_id = request.form.get("guild_id", "").strip()
    plan     = request.form.get("plan", "free").strip()

    manageable_ids = {str(g["id"]) for g in session.get("guilds", [])}
    if guild_id not in manageable_ids and not current_user.is_admin:
        abort(403)

    ok, err = db.assign_guild_plan(
        current_user.id,
        guild_id,
        plan,
        bypass_limit=current_user.is_admin,
    )
    if ok:
        flash(f"Plan updated to **{plan.capitalize()}** for that server!", "success")
    else:
        flash(err, "error")

    return redirect(url_for("main.plans"))


# ── Admin routes ──────────────────────────────────────────────────────────────

@main_bp.route("/admin")
@login_required
def admin():
    if not current_user.is_admin:
        abort(403)
    users    = db.get_all_users()
    db_stats = db.get_stats()
    return render_template("webapp/admin.html", users=users, db_stats=db_stats)


@main_bp.route("/admin/set_plan", methods=["POST"])
@login_required
def admin_set_plan():
    if not current_user.is_admin:
        abort(403)
    uid  = request.form.get("user_id", "").strip()
    plan = request.form.get("plan", "free").strip()
    if uid:
        db.set_plan(uid, plan)
        flash(f"Plan for user {uid} set to {plan.capitalize()}.", "success")
    return redirect(url_for("main.admin"))


@main_bp.route("/admin/toggle_admin", methods=["POST"])
@login_required
def admin_toggle_admin():
    if not current_user.is_admin:
        abort(403)
    uid      = request.form.get("user_id", "").strip()
    is_admin = request.form.get("is_admin") == "1"
    if uid and uid != current_user.id:   # can't demote yourself
        db.set_admin(uid, is_admin)
        flash("Admin status updated.", "success")
    return redirect(url_for("main.admin"))
