"""
Single Cog containing every music command.

Supported input types for  #play:
  • YouTube video URL          → played directly
  • YouTube playlist URL       → entire playlist queued
  • Spotify track URL          → title+artist looked up via Spotify API,
                                  then searched on YouTube and played
  • Spotify playlist URL       → all tracks looked up, each searched on YT
  • Spotify album URL          → same as playlist
  • Plain text / any other URL → searched on YouTube (default)
"""

import asyncio
import logging
from typing import List, Optional

import discord
from discord.ext import commands

import db
from player.queue_manager import Track, TrackSource, queue_manager
from player.ytplayer import (
    enqueue_and_play,
    get_current_track,
    skip_current,
    stop_all,
    _fmt_duration,
)
from search.spotify import (
    detect_type as spotify_detect_type,
    get_album_tracks,
    get_playlist_tracks as spotify_playlist_tracks,
    get_track_info,
    is_spotify_url,
)
from search.youtube import (
    get_playlist as yt_get_playlist,
    is_youtube_playlist_url,
    is_youtube_url,
    search as yt_search,
)

logger = logging.getLogger(__name__)

# Hard safety cap — even Max plan won't import more than this per playlist call
_MAX_PLAYLIST = 200


def _playlist_cap(guild_id: int) -> int:
    """Return max tracks to import from a playlist for this guild's plan."""
    plan = db.get_guild_plan(str(guild_id))
    plan_limit = db.PLAN_QUEUE_LIMITS.get(plan, 50)
    # plan_limit 0 = unlimited (Max) → use the hard safety cap
    return plan_limit if plan_limit > 0 else _MAX_PLAYLIST


class Music(commands.Cog, name="Music"):
    """🎵 Music commands"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ─── Voice helpers ────────────────────────────────────────────────────────

    async def _ensure_voice(self, ctx: commands.Context) -> bool:
        """Join the caller's voice channel. Returns False and sends an error if unable."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send(
                "Hey! You need to be in a voice channel first so I know where to join 🎵"
            )
            return False

        channel = ctx.author.voice.channel

        if ctx.voice_client:
            if ctx.voice_client.channel != channel:
                await ctx.voice_client.move_to(channel)
        else:
            try:
                await channel.connect(self_deaf=True)
            except discord.ClientException as exc:
                await ctx.send(
                    f"Hmm, I couldn't connect to that channel. "
                    f"Here's what went wrong: `{exc}`"
                )
                return False
            except asyncio.TimeoutError:
                await ctx.send(
                    "I tried to join but it took too long — the channel might be full "
                    "or I may not have permission. Could you try again?"
                )
                return False

        return True

    # ─── Commands ─────────────────────────────────────────────────────────────

    @commands.command(name="join", aliases=["j"])
    async def join(self, ctx: commands.Context):
        """Join your current voice channel."""
        if await self._ensure_voice(ctx):
            await ctx.send(
                f"I'm in! 🎉 Joined **{ctx.author.voice.channel.name}** and ready to play!"
            )

    # ------------------------------------------------------------------
    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        """
        Play a song or queue a playlist.

        Accepts:
          • YouTube URL or search term  (default)
          • YouTube playlist URL
          • Spotify track / playlist / album URL
        """
        if not await self._ensure_voice(ctx):
            return

        vc: discord.VoiceClient = ctx.voice_client
        gid: int = ctx.guild.id
        ch = ctx.channel

        query = query.strip()

        # ── Spotify ──────────────────────────────────────────────────────────
        if is_spotify_url(query):
            sp_type = spotify_detect_type(query)

            if sp_type == "track":
                async with ctx.typing():
                    info = get_track_info(query)
                if not info:
                    await ctx.send(
                        "I couldn't grab that Spotify track info — my Spotify credentials "
                        "might not be configured. Make sure `SPOTIFY_CLIENT_ID` and "
                        "`SPOTIFY_CLIENT_SECRET` are set in your `.env` file!"
                    )
                    return
                track = Track(
                    url=f"ytsearch5:{info['search_query']} official audio",
                    title=info["title"],
                    artist=info["artist"],
                    source=TrackSource.SPOTIFY,
                    requester_id=ctx.author.id,
                )
                await ctx.send(
                    f"Got it! 🎧 I'm searching YouTube for **{info['search_query']}**..."
                )
                await enqueue_and_play(vc, gid, track, ch)

            elif sp_type in ("playlist", "album"):
                async with ctx.typing():
                    raw = (
                        spotify_playlist_tracks(query)
                        if sp_type == "playlist"
                        else get_album_tracks(query)
                    )
                if not raw:
                    await ctx.send(
                        f"I couldn't load that Spotify {sp_type} — my Spotify credentials "
                        "might not be set up. Check `SPOTIFY_CLIENT_ID` and "
                        "`SPOTIFY_CLIENT_SECRET` in your `.env` file!"
                    )
                    return

                raw = raw[:_playlist_cap(ctx.guild.id)]
                await ctx.send(
                    f"Nice! 🎶 I found **{len(raw)}** tracks in that Spotify {sp_type}. "
                    "Give me a moment while I search YouTube for each one!"
                )

                tracks = [
                    Track(
                        url=f"ytsearch5:{t['search_query']}",
                        title=t["title"],
                        artist=t["artist"],
                        source=TrackSource.SPOTIFY,
                        requester_id=ctx.author.id,
                    )
                    for t in raw
                ]
                # Start the first track; bulk-add the rest to avoid chat spam.
                first, *rest = tracks
                await enqueue_and_play(vc, gid, first, ch)
                if rest:
                    queue_manager.add_many(gid, rest)
                    await ctx.send(
                        f"I've lined up **{len(rest)}** more tracks in the queue for you! 🎶"
                    )

            else:
                await ctx.send(
                    "Hmm, I'm not sure what to do with that Spotify link. "
                    "I can handle **tracks**, **playlists**, and **albums** — "
                    "could you try one of those?"
                )
            return

        # ── YouTube playlist ──────────────────────────────────────────────────
        if is_youtube_playlist_url(query):
            async with ctx.typing():
                entries = await yt_get_playlist(query)
            if not entries:
                await ctx.send(
                    "I couldn't load that YouTube playlist — it might be private, empty, "
                    "or the link could be wrong. Could you double-check and try again?"
                )
                return

            entries = entries[:_playlist_cap(ctx.guild.id)]
            await ctx.send(
                f"I found **{len(entries)}** tracks in that playlist! "
                "Loading them up now... 🎵"
            )

            tracks = [
                Track(
                    url=e["url"],
                    title=e["title"],
                    source=TrackSource.YOUTUBE,
                    requester_id=ctx.author.id,
                    duration=e.get("duration"),
                )
                for e in entries
            ]
            first, *rest = tracks
            await enqueue_and_play(vc, gid, first, ch)
            if rest:
                queue_manager.add_many(gid, rest)
                await ctx.send(
                    f"I've added **{len(rest)}** more tracks to the queue! 🎶"
                )
            return

        # ── YouTube URL or plain search ───────────────────────────────────────
        async with ctx.typing():
            info = await yt_search(query)

        if not info:
            await ctx.send(
                f"I searched everywhere but couldn't find anything for **{query}**. "
                "Maybe try a different search term or paste a direct URL?"
            )
            return

        track = Track(
            url=f"https://www.youtube.com/watch?v={info['id']}",
            title=info.get("title", "Unknown"),
            artist=info.get("uploader") or info.get("channel") or "",
            source=TrackSource.YOUTUBE,
            requester_id=ctx.author.id,
            duration=info.get("duration"),
            thumbnail=info.get("thumbnail"),
        )
        await enqueue_and_play(vc, gid, track, ch)

    # ------------------------------------------------------------------
    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        """Pause the current song."""
        vc = ctx.voice_client
        if not vc or not vc.is_playing():
            await ctx.send("There's nothing playing right now for me to pause!")
            return
        vc.pause()
        await ctx.send("Music paused! ⏸ Use `resume` whenever you're ready to continue.")

    # ------------------------------------------------------------------
    @commands.command(name="resume", aliases=["r"])
    async def resume(self, ctx: commands.Context):
        """Resume a paused song."""
        vc = ctx.voice_client
        if not vc or not vc.is_paused():
            await ctx.send("Nothing is paused right now — the music is already going! ▶️")
            return
        vc.resume()
        await ctx.send("Music is back on! ▶️ Enjoy!")

    # ------------------------------------------------------------------
    @commands.command(name="skip", aliases=["s", "next"])
    async def skip(self, ctx: commands.Context):
        """Skip the current song."""
        vc = ctx.voice_client
        if not vc:
            await ctx.send("I'm not in a voice channel right now!")
            return
        if await skip_current(vc):
            await ctx.send("Got it! ⏭ I'll play the next song now...")
        else:
            await ctx.send("There's nothing playing right now to skip!")

    # ------------------------------------------------------------------
    @commands.command(name="nowplaying", aliases=["np", "current"])
    async def now_playing(self, ctx: commands.Context):
        """Show what's currently playing."""
        track = get_current_track(ctx.guild.id)
        if not track:
            await ctx.send(
                "I'm not playing anything at the moment — use `play` to start something! 🎵"
            )
            return

        dur = _fmt_duration(track.duration)
        source_label = "Spotify → YouTube" if track.source == TrackSource.SPOTIFY else "YouTube"
        icon = "🎧" if track.source == TrackSource.SPOTIFY else "▶️"

        embed = discord.Embed(
            title=f"{icon} Now Playing",
            description=f"**{track.display_title}**{dur}",
            color=0x1DB954 if track.source == TrackSource.SPOTIFY else 0xFF0000,
        )
        embed.set_footer(text=f"Streaming from {source_label}")
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)

        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    @commands.command(name="queue", aliases=["q"])
    async def queue_cmd(self, ctx: commands.Context):
        """Show the current queue."""
        gid = ctx.guild.id
        current = get_current_track(gid)
        upcoming: List[Track] = queue_manager.list_tracks(gid)

        lines = []
        if current:
            dur = _fmt_duration(current.duration)
            lines.append(f"▶️ **Now Playing:** {current.display_title}{dur}")

        if upcoming:
            lines.append(f"\n📋 **Coming up — {len(upcoming)} track(s):**")
            for i, t in enumerate(upcoming[:15], 1):
                dur = _fmt_duration(t.duration)
                lines.append(f"`{i}.` {t.display_title}{dur}")
            if len(upcoming) > 15:
                lines.append(f"*… and {len(upcoming) - 15} more tracks waiting!*")
        elif not current:
            lines.append(
                "The queue is empty right now! Add some songs with `play` 🎵"
            )

        await ctx.send("\n".join(lines) if lines else "The queue is empty — let's add some music! 🎵")

    # ------------------------------------------------------------------
    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the upcoming queue."""
        gid = ctx.guild.id
        if queue_manager.is_empty(gid):
            await ctx.send(
                "The queue is empty right now — add some songs first and then I can shuffle them! 🎲"
            )
            return
        queue_manager.shuffle(gid)
        await ctx.send(
            f"Done! 🔀 I've shuffled **{queue_manager.size(gid)}** tracks — "
            "let's see what comes up next!"
        )

    # ------------------------------------------------------------------
    @commands.command(name="disconnect", aliases=["dc", "leave", "stop"])
    async def disconnect(self, ctx: commands.Context):
        """Stop playback, clear the queue, and disconnect."""
        vc = ctx.voice_client
        if not vc:
            await ctx.send("I'm not in a voice channel right now!")
            return
        await stop_all(vc, ctx.guild.id)
        await ctx.send(
            "Alright, I'm heading out! 👋 Queue cleared and disconnected. "
            "Come back whenever you want more music!"
        )

    # ------------------------------------------------------------------
    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, position: int):
        """Remove a track from the queue by its position number."""
        gid = ctx.guild.id
        tracks = queue_manager.list_tracks(gid)
        if not tracks:
            await ctx.send("The queue is empty — there's nothing for me to remove!")
            return
        if position < 1 or position > len(tracks):
            await ctx.send(
                f"Hmm, I only have tracks at positions **1 to {len(tracks)}**. "
                "Try one of those!"
            )
            return
        removed = queue_manager._q(gid).pop(position - 1)
        await ctx.send(f"Done! I've removed **{removed.display_title}** from the queue. 🗑")

    # ─── Auto-disconnect when left alone ──────────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot:
            return

        vc: Optional[discord.VoiceClient] = member.guild.voice_client
        if not vc or not vc.channel:
            return

        # Only act when a human left the bot's channel
        if before.channel != vc.channel:
            return

        humans = [m for m in vc.channel.members if not m.bot]
        if humans:
            return

        # Respect the auto_disconnect toggle from guild settings
        settings = db.get_guild_settings(str(member.guild.id))
        if not settings.get("auto_disconnect", 1):
            return

        # Wait 60 s then disconnect if still alone
        await asyncio.sleep(60)
        vc = member.guild.voice_client
        if vc and vc.channel:
            humans = [m for m in vc.channel.members if not m.bot]
            if not humans:
                await stop_all(vc, member.guild.id)
                logger.info(
                    "Auto-disconnected from %s (left alone for 60 s)",
                    member.guild.name,
                )


# ─── Extension entry point ────────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
