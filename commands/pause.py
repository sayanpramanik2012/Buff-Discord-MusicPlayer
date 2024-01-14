import discord

async def pause_command(ctx):
    voice_client = ctx.voice_client

    # Check if the bot is in a voice channel
    if voice_client is None:
        return await ctx.send("I'm not currently in a voice channel.")

    # Check if the bot is already paused
    if voice_client.is_paused():
        return await ctx.send("I am already paused.")

    # Pause the song
    voice_client.pause()
    await ctx.send("I am Paused. Use `resume` command to resume.")