import asyncio
import logging
import sys
import threading

import discord
from discord.ext import commands
from flask import Flask, jsonify, render_template, request

import config

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ─── Discord bot ──────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = False  # not needed; reduces privilege requirements

bot = commands.Bot(
    command_prefix=config.PREFIX,
    intents=intents,
    description="Buff Music Bot — plays YouTube & Spotify via YouTube",
)


@bot.event
async def on_ready():
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{config.PREFIX}play  |  music bot",
        )
    )


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"Looks like you forgot something! I need `{error.param.name}` to run that command. "
            f"Try `{config.PREFIX}help {ctx.command}` to see how to use it."
        )
    elif isinstance(error, commands.CommandNotFound):
        pass  # silently ignore unknown commands
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command only works inside a server — I can't do that in DMs!")
    elif isinstance(error, commands.CommandInvokeError):
        logger.error("Command %s raised: %s", ctx.command, error.original, exc_info=error.original)
        await ctx.send(
            f"Oops! Something went wrong while running that command. "
            f"Here's the details: `{error.original}`"
        )
    else:
        logger.warning("Unhandled command error: %s", error)


# ─── Flask web dashboard ──────────────────────────────────────────────────────
app = Flask(__name__)


@app.route("/")
def index():
    try:
        guild_count = len(bot.guilds) if bot.is_ready() else 0
        user_count = sum(g.member_count or 0 for g in bot.guilds) if bot.is_ready() else 0
        return render_template(
            "index.html",
            bot_is_online=bot.is_ready(),
            total_servers=guild_count,
            total_users=user_count,
            prefix=config.PREFIX,
            current_page=1,
            total_pages=1,
            total_files=0,
        )
    except Exception as exc:
        logger.error("Flask / route error: %s", exc)
        return render_template(
            "index.html",
            bot_is_online=False,
            total_servers=0,
            total_users=0,
            prefix=config.PREFIX,
            current_page=1,
            total_pages=1,
            total_files=0,
        )


@app.route("/api/status")
def api_status():
    return jsonify(
        {
            "online": bot.is_ready(),
            "guilds": len(bot.guilds) if bot.is_ready() else 0,
            "users": sum(g.member_count or 0 for g in bot.guilds) if bot.is_ready() else 0,
        }
    )


@app.route("/api/songs")
def api_songs():
    # Streaming-only bot — no local cache; return empty for dashboard compatibility
    return jsonify({"songs": [], "total_files": 0, "total_pages": 0})


def _run_flask():
    app.run(host="0.0.0.0", port=config.FLASK_PORT, debug=False, use_reloader=False)


# ─── Entry point ─────────────────────────────────────────────────────────────
async def main():
    async with bot:
        await bot.load_extension("commands.music")
        logger.info("Music cog loaded")

        flask_thread = threading.Thread(target=_run_flask, daemon=True)
        flask_thread.start()
        logger.info("Flask dashboard started on port %s", config.FLASK_PORT)

        await bot.start(config.TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested — goodbye!")
