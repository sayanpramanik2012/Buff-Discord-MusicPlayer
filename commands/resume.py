async def resume_command(ctx):
    voice_client = ctx.voice_client

    # Check if the bot is in a voice channel
    if voice_client is None:
        return await ctx.send("I'm not currently in a voice channel.")

    # Check if the bot is not paused
    if not voice_client.is_paused():
        return await ctx.send("I am not paused.")

    # Resume the song
    voice_client.resume()
    await ctx.send("Resuming....")