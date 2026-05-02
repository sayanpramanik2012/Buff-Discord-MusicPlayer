import asyncio
import logging
import sys
import threading

import discord
from discord.ext import commands

import config
import db

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ─── Dynamic prefix (falls back to config.PREFIX in DMs / on error) ──────────
async def _get_prefix(bot: commands.Bot, message: discord.Message) -> str:
    if message.guild:
        return db.get_guild_prefix(str(message.guild.id))
    return config.PREFIX


# ─── Discord bot ──────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = False

bot = commands.Bot(
    command_prefix=_get_prefix,
    intents=intents,
    description="Buff Music Bot — plays YouTube & Spotify via YouTube",
)


@bot.event
async def on_ready():
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    db.init_db()
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{config.PREFIX}play  |  music bot",
        )
    )


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MissingRequiredArgument):
        prefix = await _get_prefix(bot, ctx.message)
        await ctx.send(
            f"Looks like you forgot something! I need `{error.param.name}` to run that command. "
            f"Try `{prefix}help {ctx.command}` to see how to use it."
        )
    elif isinstance(error, commands.CommandNotFound):
        pass
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
def _run_flask(flask_app):
    flask_app.run(host="0.0.0.0", port=config.FLASK_PORT, debug=False, use_reloader=False)


# ─── Entry point ─────────────────────────────────────────────────────────────
async def main():
    db.init_db()

    async with bot:
        await bot.load_extension("commands.music")
        logger.info("Music cog loaded")

        # Import here so db.init_db() runs first
        from webapp import create_app
        flask_app = create_app(bot)

        flask_thread = threading.Thread(target=_run_flask, args=(flask_app,), daemon=True)
        flask_thread.start()
        logger.info("Flask dashboard started on port %s", config.FLASK_PORT)

        await bot.start(config.TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown requested — goodbye!")
