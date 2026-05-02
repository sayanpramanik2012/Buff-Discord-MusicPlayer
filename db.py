"""
Shared SQLite database layer.
Used by both the Flask web app (web requests) and the Discord bot (async, via executor).
Each function opens its own connection so it's safe to call from any thread.
"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("./data/buff.db")

# ── Plan limits ───────────────────────────────────────────────────────────────
PLAN_SERVER_LIMITS = {"free": 0, "pro": 2, "max": 10}
PLAN_QUEUE_LIMITS  = {"free": 50, "pro": 200, "max": 0}  # 0 = unlimited


# ── Connection factory ────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db() -> None:
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                username      TEXT NOT NULL,
                discriminator TEXT DEFAULT '0',
                avatar        TEXT,
                is_admin      INTEGER DEFAULT 0,
                created_at    TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT NOT NULL REFERENCES users(id),
                plan        TEXT NOT NULL DEFAULT 'free',
                status      TEXT NOT NULL DEFAULT 'active',
                started_at  TEXT DEFAULT (datetime('now')),
                expires_at  TEXT,
                payment_ref TEXT
            );

            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id           TEXT PRIMARY KEY,
                guild_name         TEXT,
                guild_icon         TEXT,
                prefix             TEXT DEFAULT '#',
                dj_role_id         TEXT,
                volume             INTEGER DEFAULT 100,
                max_queue_length   INTEGER DEFAULT 50,
                auto_disconnect    INTEGER DEFAULT 1,
                announce_songs     INTEGER DEFAULT 1,
                updated_at         TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS guild_plans (
                guild_id    TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL REFERENCES users(id),
                plan        TEXT NOT NULL,
                assigned_at TEXT DEFAULT (datetime('now'))
            );
        """)


# ── User helpers ──────────────────────────────────────────────────────────────

def upsert_user(
    user_id: str,
    username: str,
    discriminator: str,
    avatar: Optional[str],
    admin_ids: Optional[List[str]] = None,
) -> None:
    is_admin = 1 if (admin_ids and user_id in admin_ids) else 0
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO users (id, username, discriminator, avatar, is_admin)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                username      = excluded.username,
                discriminator = excluded.discriminator,
                avatar        = excluded.avatar,
                is_admin      = MAX(is_admin, excluded.is_admin)
            """,
            (user_id, username, discriminator, avatar, is_admin),
        )
        # Ensure a subscription row exists
        conn.execute(
            "INSERT OR IGNORE INTO subscriptions (user_id, plan, status) VALUES (?, 'free', 'active')",
            (user_id,),
        )


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# ── Subscription helpers ──────────────────────────────────────────────────────

def get_subscription(user_id: str) -> Dict[str, Any]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    return dict(row) if row else {"plan": "free", "status": "active", "user_id": user_id}


def set_plan(user_id: str, plan: str, expires_at: Optional[str] = None, payment_ref: Optional[str] = None) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE subscriptions SET status = 'cancelled' WHERE user_id = ? AND status = 'active'",
            (user_id,),
        )
        conn.execute(
            "INSERT INTO subscriptions (user_id, plan, status, expires_at, payment_ref) VALUES (?, ?, 'active', ?, ?)",
            (user_id, plan, expires_at, payment_ref),
        )


# ── Guild settings helpers ────────────────────────────────────────────────────

_DEFAULTS: Dict[str, Any] = {
    "prefix": "#",
    "dj_role_id": None,
    "volume": 100,
    "max_queue_length": 50,
    "auto_disconnect": 1,
    "announce_songs": 1,
}


def get_guild_settings(guild_id: str) -> Dict[str, Any]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)).fetchone()
    if row:
        return dict(row)
    return {"guild_id": guild_id, **_DEFAULTS}


def update_guild_settings(guild_id: str, **kwargs) -> None:
    current = get_guild_settings(guild_id)
    current.update(kwargs)
    current["guild_id"] = guild_id
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO guild_settings
                (guild_id, guild_name, guild_icon, prefix, dj_role_id, volume,
                 max_queue_length, auto_disconnect, announce_songs)
            VALUES
                (:guild_id, :guild_name, :guild_icon, :prefix, :dj_role_id, :volume,
                 :max_queue_length, :auto_disconnect, :announce_songs)
            ON CONFLICT(guild_id) DO UPDATE SET
                guild_name       = excluded.guild_name,
                guild_icon       = excluded.guild_icon,
                prefix           = excluded.prefix,
                dj_role_id       = excluded.dj_role_id,
                volume           = excluded.volume,
                max_queue_length = excluded.max_queue_length,
                auto_disconnect  = excluded.auto_disconnect,
                announce_songs   = excluded.announce_songs,
                updated_at       = datetime('now')
            """,
            current,
        )


def get_guild_prefix(guild_id: str) -> str:
    return get_guild_settings(guild_id).get("prefix", "#")


# ── Guild plan helpers ────────────────────────────────────────────────────────

def get_guild_plan(guild_id: str) -> str:
    with _conn() as conn:
        row = conn.execute("SELECT plan FROM guild_plans WHERE guild_id = ?", (guild_id,)).fetchone()
    return row["plan"] if row else "free"


def get_user_assigned_guilds(user_id: str) -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT guild_id, plan FROM guild_plans WHERE user_id = ?", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def assign_guild_plan(user_id: str, guild_id: str, plan: str, bypass_limit: bool = False) -> tuple:
    """
    Assign *plan* to *guild_id* for *user_id*.
    Returns (success: bool, error_message: str | None).
    """
    if plan == "free":
        with _conn() as conn:
            conn.execute("DELETE FROM guild_plans WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
        return True, None

    if not bypass_limit:
        sub = get_subscription(user_id)
        user_plan = sub.get("plan", "free")
        max_srv = PLAN_SERVER_LIMITS.get(user_plan, 0)

        if max_srv == 0:
            return False, "You need a Pro or Max subscription to assign plans to servers."
        if plan == "max" and user_plan == "pro":
            return False, "You need a Max subscription to assign the Max plan."

        assigned = get_user_assigned_guilds(user_id)
        already_has = any(g["guild_id"] == guild_id for g in assigned)
        if not already_has and len(assigned) >= max_srv:
            return False, f"You've used all {max_srv} server slot(s) for your {user_plan.capitalize()} plan."

    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO guild_plans (guild_id, user_id, plan)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET user_id = excluded.user_id, plan = excluded.plan, assigned_at = datetime('now')
            """,
            (guild_id, user_id, plan),
        )
    return True, None


# ── Admin helpers ─────────────────────────────────────────────────────────────

def get_all_users(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT u.*, COALESCE(s.plan, 'free') AS plan, COALESCE(s.status, 'active') AS sub_status
            FROM users u
            LEFT JOIN subscriptions s ON s.user_id = u.id AND s.status = 'active'
            ORDER BY u.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def set_admin(user_id: str, is_admin: bool) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET is_admin = ? WHERE id = ?", (int(is_admin), user_id))


def get_stats() -> Dict[str, int]:
    with _conn() as conn:
        users   = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        pro     = conn.execute("SELECT COUNT(*) FROM subscriptions WHERE plan != 'free' AND status = 'active'").fetchone()[0]
        guilds  = conn.execute("SELECT COUNT(*) FROM guild_settings").fetchone()[0]
        premium = conn.execute("SELECT COUNT(*) FROM guild_plans").fetchone()[0]
    return {"users": users, "paid": pro, "guilds": guilds, "premium_guilds": premium}
