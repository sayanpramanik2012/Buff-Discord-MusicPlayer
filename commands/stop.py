# disconnect.py
import discord

async def stop_command(ctx):
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)

    if voice_channel_client:
        # Stop playing and disconnect from the voice channel
        voice_channel_client.stop()

        await ctx.send("Bot disconnected and reset to initial state.")
    else:
        await ctx.send("Bot is not currently in a voice channel.")