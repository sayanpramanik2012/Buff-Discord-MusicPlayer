# commands/join.py
import logging

logger = logging.getLogger(__name__)

async def join_command(ctx):
    """Join the user's voice channel"""
    # Check if the user is in a voice channel
    if ctx.message.author.voice is None:
        await ctx.send("❌ Please join a voice channel first!")
        return False
    
    author_voice_channel = ctx.message.author.voice.channel
    
    # Check if the bot is already in a voice channel
    if ctx.voice_client is not None:
        if ctx.guild.me.voice.channel != author_voice_channel:
            await ctx.send("❌ I'm already in another voice channel!")
            return False
        else:
            # Bot is already in the same channel
            logger.info(f"Already in {author_voice_channel.name}")
            return True
    
    try:
        # Bot joins the user's voice channel
        voice_client = await author_voice_channel.connect()
        
        # Deafen the bot
        await voice_client.guild.change_voice_state(
            channel=author_voice_channel, 
            self_deaf=True
        )
        
        await ctx.send(f"🔊 Joined **{author_voice_channel.name}**!")
        logger.info(f"Joined voice channel: {author_voice_channel.name}")
        return True
    
    except Exception as e:
        logger.error(f"Error joining voice channel: {e}")
        await ctx.send("❌ Failed to join voice channel.")
        return False
