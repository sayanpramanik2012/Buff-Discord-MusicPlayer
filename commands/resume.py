# commands/resume.py
import logging

logger = logging.getLogger(__name__)

async def resume_command(ctx):
    """Resume the paused song"""
    voice_client = ctx.voice_client
    
    # Check if the bot is in a voice channel
    if voice_client is None:
        return await ctx.send("❌ I'm not in a voice channel.")
    
    # Check if the bot is paused
    if not voice_client.is_paused():
        if voice_client.is_playing():
            return await ctx.send("▶️ Already playing.")
        else:
            return await ctx.send("❌ Nothing to resume.")
    
    # Resume the song
    voice_client.resume()
    logger.info(f"Resumed playback in guild {ctx.guild.id}")
    await ctx.send("▶️ Resumed!")
