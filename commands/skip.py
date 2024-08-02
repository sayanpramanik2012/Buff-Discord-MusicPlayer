# skip.py
from discord.ext import commands
from player import ytplayer
import discord

async def skip_command(ctx):
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)

    if voice_channel_client and voice_channel_client.is_playing():
        # Stop the current song and proceed to the next one
        await ctx.send("Skipped to the next song.")
        await ytplayer.on_song_end(ctx, "")  # Pass an empty string as the audio_url (not used in on_song_end)
    else:
        await ctx.send("There is no song playing to skip.")
