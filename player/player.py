# player.py
from collections import deque
import discord
from pytube import YouTube
song_queues = {}
import asyncio
import youtube_dl

async def play_audio(ctx, audio_url):
    # Get the voice channel of the command author
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)

    # Wrapper function to schedule the coroutine
    def after_play(error):
        coro = on_song_end(ctx, audio_url)
        fut = asyncio.run_coroutine_threadsafe(coro, ctx.bot.loop)
        try:
            fut.result()
        except:
            pass

    # Check if the bot is not already playing something
    if not voice_channel_client.is_playing()and ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
        audio_url = song_queues[ctx.guild.id].popleft()
        await ctx.send(f"Now playing: {audio_url}")
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

            audio_settings = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn -b:a 128k -af "bass=g=1,treble=g=1,volume=1"',  # Adjust bitrate for higher quality
            }

            # Play the audio with enhanced settings
            voice_channel_client.play(discord.FFmpegPCMAudio(audio_stream_url, **audio_settings), after=after_play)

            # await ctx.send(f"Now playing: {audio_url}")
        except Exception as e:
            print(f"Error: {e}")
            await ctx.send("Failed to play the audio. Please check the provided YouTube link.")

            # Check if there are more songs in the queue and #skip command is not used
            if len(song_queues)>1 and not ctx.message.content.startswith("#skip"):
                await play_audio(ctx, audio_url)
    else:
        await ctx.send("I'm already playing something. Please wait for the current song to finish.")
        if not ctx.message.content.startswith("#skip"):
            await enqueue_song(ctx, audio_url)

async def on_song_end(ctx, audio_url):
    # Check if there are more songs in the queue
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    
    if voice_channel_client and voice_channel_client.is_playing() and ctx.message.content.startswith("#skip"):
        voice_channel_client.stop()

    if not ctx.message.content.startswith("#skip"):
        if ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
            await play_audio(ctx, audio_url)
        else:
            # If the queue is empty, disconnect from the voice channel
            if voice_channel_client and voice_channel_client.is_connected():
                await voice_channel_client.disconnect()
                print("------------------song over------------------")


async def enqueue_song(ctx, audio_url):
    # Ensure there is a queue for the server
    if ctx.guild.id not in song_queues:
        song_queues[ctx.guild.id] = deque()

    # Enqueue the song and notify the user
    song_queues[ctx.guild.id].append((audio_url))
    if discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_playing():
        await ctx.send(f"Added to queue: {audio_url}")

    # If the bot is not already playing, start playing the next song in the queue
    if len(song_queues)==1 and not discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_playing():
        await play_audio(ctx, audio_url)