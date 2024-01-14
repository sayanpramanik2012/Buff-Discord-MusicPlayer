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

# Event listener for when the bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

# Command handling JOIN
@bot.command(name='join')
async def joinCommand(ctx):
    await join.join_command(ctx)

# Command handling PLAY
@bot.command(name='play')
async def playCommand(ctx,*args):
    url = ' '.join(args)
    await play.play_command(ctx,url)

@bot.command(name='disconnect')
async def disconnectCommand(ctx):
    await disconnect.disconnect_command(ctx)

@bot.command(name='pause')
async def pauseCommand(ctx):
    await pause.pause_command(ctx)

@bot.command(name='resume')
async def resumeCommand(ctx):
    await resume.resume_command(ctx)

@bot.command(name='skip')
async def skipCommand(ctx):
    await skip.skip_command(ctx)

# @bot.event
# async def on_voice_state_update(member, before, after,ctx):
#     if member == bot.user:  # Check if the bot's voice state has changed
#         if before.channel and not after.channel:  # Bot has been disconnected
#             print("Bot disconnected from voice channel by force, attempting to reconnect...")
            
#             # Add your logic here to disconnect the bot
#             await disconnect.disconnect_command(ctx)


# Run the bot with the token
bot.run(TOKEN)

