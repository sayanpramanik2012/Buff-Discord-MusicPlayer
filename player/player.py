# player.py
from collections import deque
import discord
from pytube import YouTube
song_queues = {}
import asyncio
import youtube_dl

async def play_audio(ctx, audio_url):
    # Each guild should have its own voice client
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if not voice_client:
        await ctx.send("I am not connected to a voice channel.")
        return

    def after_play(error):
        # Error handling and executing the next song in the queue
        if error:
            print(f'Error in playback: {error}')
        asyncio.run_coroutine_threadsafe(on_song_end(ctx,audio_url), ctx.bot.loop)

    if not voice_client.is_playing():
        # Play the next song from the queue
        if ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
            audio_url = song_queues[ctx.guild.id].popleft()
            await ctx.send(f"Playing: {audio_url}")

            try:
                try:
                    # Extract audio stream URL using youtube_dl
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'quiet': True
                    }
                    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(audio_url, download=False)
                        audio_stream_url = info['url']
                    
                except Exception as e:
                    # Extract audio stream URL using pytube
                    yt = YouTube(audio_url)
                    audio_stream_url = yt.streams.filter(only_audio=True).first()

                audio_settings = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                                  'options': '-vn -b:a 128k -af "bass=g=1,treble=g=1,volume=1"'}
                voice_client.play(discord.FFmpegPCMAudio(audio_stream_url, **audio_settings), after=after_play)
            except Exception as e:
                await ctx.send(f"Error: {e}")
        else:
            await ctx.send("No more songs in the queue.")
    else:
        await ctx.send("I'm already playing music.")

async def on_song_end(ctx, audio_url):
    # Check if there are more songs in the queue
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    
    if voice_channel_client and voice_channel_client.is_playing() and ctx.message.content.startswith("#skip"):
        voice_channel_client.stop()

    if not ctx.message.content.startswith("#skip"):
        if ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
            if not ctx.message.content.startswith("#disconnect"):
                await play_audio(ctx, audio_url)
        else:
            await ctx.send("No more song in Queue, Bye")
            # If the queue is empty, disconnect from the voice channel
            if voice_channel_client and voice_channel_client.is_connected():
                await disconnect_and_clear_queue(ctx)
                await voice_channel_client.disconnect()


async def enqueue_song(ctx, audio_url,from_playlist):
    
    # Ensure there is a queue for the server
    if ctx.guild.id not in song_queues:
        song_queues[ctx.guild.id] = deque()

    # Enqueue the song and notify the user
    song_queues[ctx.guild.id].append((audio_url))
    if not from_playlist:
        if discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_playing() or discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_paused():
            await ctx.send(f"I am Adding to queue: {audio_url}")
        if discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_paused():
            await ctx.send(f"Currently I am paused use `resume` to resume")
    # If the bot is not already playing, start playing the next song in the queue
    if len(song_queues[ctx.guild.id]) == 1 and not discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_playing() and not discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_paused():
        await play_audio(ctx, audio_url)

async def disconnect_and_clear_queue(ctx):
    # Disconnect from the voice channel and clear the queue for the guild
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if voice_channel_client and voice_channel_client.is_connected():
        await voice_channel_client.disconnect()
    if ctx.guild.id in song_queues:
        del song_queues[ctx.guild.id]
    print(f"Disconnected and cleared queue for Guild ID: {ctx.guild.id}")