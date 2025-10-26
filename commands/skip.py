# commands/skip.py
from player import ytplayer
import discord
import logging

logger = logging.getLogger(__name__)

async def skip_command(ctx):
    """Skip the current song"""
    await ytplayer.skip_song(ctx)
