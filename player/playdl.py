# player.py
import discord
from discord.ext import commands
from playdl import play_dl

async def play_audio(ctx, audio_url):
    # Get the voice channel of the command author
    voice_channel = ctx.message.author.voice.channel
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)

    # Check if the bot is not already playing something
    if not voice_channel_client.is_playing():
        try:
            # Fetch audio stream URL using play-dl
            info = await play_dl(f"{audio_url}", return_info=True)
            audio_stream_url = info['formats'][0]['url']

            # Play the audio
            voice_channel_client.play(discord.FFmpegPCMAudio(audio_stream_url), after=lambda e: on_song_end(ctx))

            await ctx.send(f"Now playing: {audio_url}")
        except Exception as e:
            print(f"Error: {e}")
            await ctx.send("Failed to play the audio. Please check the provided YouTube link.")
    else:
        await ctx.send("I'm already playing something. Please wait for the current song to finish.")

def on_song_end(ctx):
    # You can add logic here for what should happen when a song ends
    pass
