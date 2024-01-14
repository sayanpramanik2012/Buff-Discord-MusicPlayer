# disconnect.py
import discord

async def disconnect_command(ctx):
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if voice_channel_client:
        # Stop playing and disconnect from the voice channel
        voice_channel_client.stop()
        await voice_channel_client.disconnect()

        # Set any other state variables to initial values if needed
        # For example, you might want to reset a queue or clear any active states

        await ctx.send("I am disconnected.")
    else:
        await ctx.send("I am not in a voice channel.")