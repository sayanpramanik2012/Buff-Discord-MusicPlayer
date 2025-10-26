# commands/disconnect.py
import discord
from player import ytplayer
import logging

logger = logging.getLogger(__name__)

async def disconnect_command(ctx):
    """Disconnect from voice channel and clear queue"""
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    
    if voice_channel_client:
        # Clear queue and disconnect
        await ytplayer.disconnect_and_clear_queue(ctx)
        await ctx.send("👋 Disconnected and cleared queue.")
        logger.info(f"Disconnected from voice in guild {ctx.guild.id}")
    else:
        await ctx.send("❌ I'm not in a voice channel.")
