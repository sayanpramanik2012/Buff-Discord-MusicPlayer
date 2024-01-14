async def join_command(ctx):
    # Check if the user is in a voice channel
    if ctx.message.author.voice is None:
        return await ctx.send("Please join a voice channel to allow me to connect!")

    author_voice_channel = ctx.message.author.voice.channel

    # Check if the bot is already in a voice channel
    if ctx.voice_client is not None and ctx.guild.me.voice.channel != author_voice_channel:
        return await ctx.send("I'm already in another voice channel!")

    # Check if the bot and user are in the same server and voice channel
    bot_in_same_channel = (
        ctx.guild.me.voice is not None
        and ctx.guild.me.voice.channel == author_voice_channel
    )
    if bot_in_same_channel:
        return

    # Bot joins the user's voice channel
    voice_client = await author_voice_channel.connect()

    # Deafen the bot
    await voice_client.guild.change_voice_state(channel=author_voice_channel, self_deaf=True)

    await ctx.send(f"Joined {author_voice_channel}!")
