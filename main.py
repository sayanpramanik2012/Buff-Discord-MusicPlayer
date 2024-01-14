import discord
from discord.ext import commands
import youtube_dl
from commands import join, pause, play, disconnect, skip, resume
from search import youtube
import os

# Load bot token from config file
from config import TOKEN

# Create intents
intents = discord.Intents.all()

# Create a bot instance with intents
bot = commands.Bot(command_prefix='#', intents=intents)
bot.voice_contexts = {}

# Event listener for when the bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

# Command handling JOIN
@bot.command(name='join')
async def joinCommand(ctx):
    bot.voice_contexts[ctx.guild.id] = ctx
    await join.join_command(ctx)

# Command handling PLAY
@bot.command(name='play')
async def playCommand(ctx,*args):
    bot.voice_contexts[ctx.guild.id] = ctx
    url = ' '.join(args)
    await play.play_command(ctx,url)

@bot.command(name='disconnect')
async def disconnectCommand(ctx):
    await disconnect.disconnect_command(ctx)
    bot.voice_contexts.pop(ctx.guild.id, None)

@bot.command(name='pause')
async def pauseCommand(ctx):
    await pause.pause_command(ctx)

@bot.command(name='resume')
async def resumeCommand(ctx):
    await resume.resume_command(ctx)

@bot.command(name='skip')
async def skipCommand(ctx):
    await skip.skip_command(ctx)

@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user and before.channel is not None and after.channel is None:
        print("You disconnected me from voice channel by force, u can use again after 1min.")
        print(bot.voice_contexts)
        # guild_id = before.channel.id
        # if guild_id in bot.voice_contexts:
        #     ctx = bot.voice_contexts[guild_id]
        #     ctx.send("You disconnected me from voice channel by force, u can use again after 1min.")
        #     await disconnect.disconnect_command(ctx)
        #     bot.voice_contexts.pop(guild_id, None)  # Remove the stored context


# Run the bot with the token
bot.run(TOKEN)

