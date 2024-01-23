import discord
from discord.ext import commands,tasks
import youtube_dl
from commands import join, pause, play, disconnect, skip, resume
from search import youtube
from player import player
import os
import asyncio
# import discord_slash

# Load bot token from config file
from config import TOKEN

# Create intents
intents = discord.Intents.all()

# Create a bot instance with intents
bot = commands.Bot(command_prefix='#', intents=intents)
bot.voice_contexts = {}
# slash = discord_slash.SlashCommand(bot, sync_commands=True)



@tasks.loop(seconds=10)  # Update every 10sec
async def update_status():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"{len(bot.voice_contexts)} servers"))

# Event listener for when the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    update_status.start()

# @bot.command(name="try")
# async def try_commands(ctx):
#     embed = discord.Embed(
#         title="Try my commands!",
#         description="Here are some things I can do:"
#     )
#     for command in slash.commands:
#         embed.add_field(name=command.name, value=command.description)
#     await ctx.send(embed=embed)

# Command handling JOIN
@bot.command(name='join',help='Joins the voice channel')
async def joinCommand(ctx):
    try:
        bot.voice_contexts[ctx.guild.id] = ctx
        await join.join_command(ctx)
    except Exception as e:
        await disconnect.disconnect_command(ctx)
        bot.voice_contexts.pop(ctx.guild.id, None)
        bot.voice_contexts[ctx.guild.id] = ctx
        await join.join_command(ctx)

# Command handling PLAY
@bot.command(name='play',help='Used to play songs')
async def playCommand(ctx,*args):
    try:
        bot.voice_contexts[ctx.guild.id] = ctx
        url = ' '.join(args)
        await play.play_command(ctx,url)
    except Exception as e:
        await disconnect.disconnect_command(ctx)
        bot.voice_contexts.pop(ctx.guild.id, None)
        bot.voice_contexts[ctx.guild.id] = ctx
        url = ' '.join(args)
        await play.play_command(ctx,url)

@bot.command(name='disconnect', help='Disconnects the bot from the voice channel')
async def disconnectCommand(ctx):
    await disconnect.disconnect_command(ctx)
    bot.voice_contexts.pop(ctx.guild.id, None)

@bot.command(name='stop',help='Disconnects the bot from the voice channel')
async def disconnectCommand(ctx):
    await disconnect.disconnect_command(ctx)
    bot.voice_contexts.pop(ctx.guild.id, None)

@bot.command(name='pause',help='Pause the bot while playing')
async def pauseCommand(ctx):
    await pause.pause_command(ctx)

@bot.command(name='resume',help='Resume the bot while paused')
async def resumeCommand(ctx):
    await resume.resume_command(ctx)

@bot.command(name='skip',help='Skip to next song')
async def skipCommand(ctx):
    await skip.skip_command(ctx)

@bot.command(name='shuffle',help='Shuffles your queue')
async def shuffle_command(ctx):
    await player.shuffle_queue(ctx)

@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and before.channel is not None and after.channel is None:
        guild = before.channel.guild
        guild_id = guild.id

        # Handle the bot being forcibly disconnected
        if guild_id in player.song_queues:
            voice_channel_client = discord.utils.get(bot.voice_clients, guild=guild.name)

            # Clear the queue for the guild
            del player.song_queues[guild_id]

            # Optional: Notify users about the disconnection and queue clearance
            text_channels = guild.text_channels
            if text_channels:
                notification_channel = discord.utils.get(text_channels, name=before.channel.name)
                if notification_channel:
                    await notification_channel.send("I have been forcibly disconnected, and I will clear queue too.")
                else:
                    print(f"force disconnected from {guild.name}")

# @bot.event
# async def on_disconnect():
#     print("Disconnected from Discord. Reconnecting...")
#     await asyncio.sleep(2)  # Wait for a few seconds before attempting to reconnect
#     await bot.login(TOKEN, bot=True)
#     await bot.connect()



# Run the bot with the token
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"An error occurred: {e}")

