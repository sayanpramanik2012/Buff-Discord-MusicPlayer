import discord
import asyncio
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy
import requests
from collections import deque
# import discord
song_queues = {}
import asyncio
from random import shuffle
from config import SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET

# Spotify setup
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))

async def play_spotify_track(ctx, track_url):
    # Each guild should have its own voice client
    voice_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if not voice_client:
        await ctx.send("I am not connected to a voice channel.")
        return

    def after_play(error):
        # Error handling and executing the next song in the queue
        if error:
            print(f'Error in playback: {error}')
        asyncio.run_coroutine_threadsafe(on_song_end(ctx, track_url), ctx.bot.loop)


    if not voice_client.is_playing():
        if ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
            track_url = song_queues[ctx.guild.id].popleft()  # Get and remove the track URL from the queue
            track_id = track_url.split('/')[-1]  # Extract the track ID from the URL
            await asyncio.sleep(2)
            try:
                track_info = sp.track(track_id)
                audio_stream_url = track_info['preview_url']  # Spotify provides a preview URL for tracks
                print(audio_stream_url)
            except Exception as e:
                await ctx.send(f"Error fetching track info: {e}")
                return

            if not audio_stream_url:
                await ctx.send("Preview URL not available for this track.")
                return

            audio_settings = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                              'options': '-vn -b:a 128k -af "bass=g=1,treble=g=1,volume=1"'}
            voice_client.play(discord.FFmpegPCMAudio(audio_stream_url, **audio_settings), after=after_play)
            print(f"Playing: {track_info['name']} by {track_info['artists'][0]['name']}")
            await ctx.send(f"Playing: {track_info['name']} by {track_info['artists'][0]['name']}")
        else:
            await ctx.send("No more songs in the queue.")
    else:
        await ctx.send("I'm already playing music.")


async def on_song_end(ctx, track_url):
    # Check if there are more songs in the queue
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)

    if voice_channel_client and voice_channel_client.is_playing() and ctx.message.content.startswith("#skip"):
        voice_channel_client.stop()

    if not ctx.message.content.startswith("#skip"):
        if ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
            if not ctx.message.content.startswith("#disconnect"):
                if len(voice_channel_client.channel.members) > 1:
                    await play_spotify_track(ctx, track_url)
                else:
                    await ctx.send(f"I am not going to play the next song, No one is there with me.")
                    await disconnect_and_clear_queue(ctx)
                    await voice_channel_client.disconnect()
        else:
            await ctx.send("No more song in Queue, Bye")
            # If the queue is empty, disconnect from the voice channel
            if voice_channel_client and voice_channel_client.is_connected():
                await disconnect_and_clear_queue(ctx)
                await voice_channel_client.disconnect()

async def enqueue_spotify_track(ctx, track_url):
    # Ensure there is a queue for the server
    if ctx.guild.id not in song_queues:
        song_queues[ctx.guild.id] = deque()

    # Enqueue the track and notify the user
    song_queues[ctx.guild.id].append((track_url))
    if discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_playing() or discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_paused():
        await ctx.send(f"I am Adding to queue: {track_url}")
    if discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_paused():
        await ctx.send(f"Currently I am paused use resume to resume")
    # If the bot is not already playing, start playing the next song in the queue
    if len(song_queues[ctx.guild.id]) == 1 and not discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_playing() and not discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild).is_paused():
        await play_spotify_track(ctx, track_url)

async def disconnect_and_clear_queue(ctx):
    # Disconnect from the voice channel and clear the queue for the guild
    voice_channel_client = discord.utils.get(ctx.bot.voice_clients, guild=ctx.guild)
    if voice_channel_client and voice_channel_client.is_connected():
        await voice_channel_client.disconnect()
    if ctx.guild.id in song_queues:
        del song_queues[ctx.guild.id]
    print(f"Disconnected and cleared queue for Guild ID: {ctx.guild.id}")

async def shuffle_queue(ctx):
    # Shuffle the songs in the queue for the guild
    if ctx.guild.id in song_queues and song_queues[ctx.guild.id]:
        queue = list(song_queues[ctx.guild.id])
        shuffle(queue)
        song_queues[ctx.guild.id] = deque(queue)
        await ctx.send("Queue shuffled successfully!")
    else:
        await ctx.send("No songs in the queue to shuffle.")
