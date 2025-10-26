# commands/pause.py
import discord
import logging

logger = logging.getLogger(__name__)

async def pause_command(ctx):
    """Pause the currently playing song"""
    voice_client = ctx.voice_client
    
    # Check if the bot is in a voice channel
    if voice_client is None:
        return await ctx.send("❌ I'm not in a voice channel.")
    
    # Check if the bot is playing
    if not voice_client.is_playing():
        return await ctx.send("❌ Nothing is currently playing.")
    
    # Check if the bot is already paused
    if voice_client.is_paused():
        return await ctx.send("⏸️ Already paused.")
    
    # Pause the song
    voice_client.pause()
    logger.info(f"Paused playback in guild {ctx.guild.id}")
    await ctx.send("⏸️ Paused. Use `=resume` to continue.")
