# disconnect.py
import discord
from player import player

async def disconnect_command(ctx):
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if voice_channel_client:
        await ctx.send("I am disconnected.")
        await player.disconnect_and_clear_queue(ctx)
        # Stop playing and disconnect from the voice channel
        voice_channel_client.stop()
        await voice_channel_client.disconnect()

        # Set any other state variables to initial values if needed
        # For example, you might want to reset a queue or clear any active states

        
    else:
        await ctx.send("I am not in a voice channel.")