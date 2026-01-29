import discord
from discord import app_commands

from utils.client import setup_client
from utils.music import (
    extract_playlist_entry_urls,
    format_duration,
    get_guild_state,
    resolve_track,
    resolve_tracks_concurrently,
)

client, tree = setup_client()


def _user_voice_channel(
    interaction: discord.Interaction,
) -> discord.VoiceChannel | None:
    if not interaction.guild:
        return None
    if not interaction.user:
        return None
    voice = getattr(interaction.user, "voice", None)
    if not voice or not voice.channel:
        return None
    if isinstance(voice.channel, discord.VoiceChannel):
        return voice.channel
    return None


@tree.command(name="join", description="Join your current voice channel")
async def join(interaction: discord.Interaction):
    channel = _user_voice_channel(interaction)
    if channel is None or interaction.guild is None:
        await interaction.response.send_message(
            "Join a voice channel first.", ephemeral=True
        )
        return

    state = get_guild_state(interaction.guild)
    await state.connect(channel)
    await interaction.response.send_message(
        f"Joined **{channel.name}**.", ephemeral=True
    )


@tree.command(name="play", description="Play a song from a URL or search term")
@app_commands.describe(query="YouTube URL or search (e.g. 'never gonna give you up')")
async def play(interaction: discord.Interaction, query: str):
    if interaction.guild is None:
        await interaction.response.send_message(
            "This only works in a server.", ephemeral=True
        )
        return

    channel = _user_voice_channel(interaction)
    if channel is None:
        await interaction.response.send_message(
            "Join a voice channel first.", ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

    state = get_guild_state(interaction.guild)
    await state.connect(channel)

    # Set text channel for now playing messages
    if interaction.channel:
        state.set_text_channel(interaction.channel)
        print(
            f"DEBUG: Set text channel to {interaction.channel.name} (type: {type(interaction.channel).__name__})"
        )
    else:
        print(f"DEBUG: No interaction.channel available")

    # Fast path: playlists
    try:
        is_playlist, entry_urls, playlist_title = await extract_playlist_entry_urls(
            query, max_tracks=50
        )
    except Exception:
        is_playlist, entry_urls, playlist_title = False, [], None

    if is_playlist and entry_urls:
        try:
            first_track = await resolve_track(entry_urls[0], interaction.user)
        except Exception as e:
            await interaction.followup.send(f"Could not load that playlist: {e}")
            return

        await state.enqueue(first_track)
        await state.play_next()

        remaining_urls = entry_urls[1:]
        title_part = f"**{playlist_title}**" if playlist_title else "playlist"
        await interaction.followup.send(
            f"Queued {title_part}: **1**/{len(entry_urls)} loaded. "
            f"Loading remaining **{len(remaining_urls)}** in background (cap 50)."
        )

        async def _load_rest() -> None:
            tracks = await resolve_tracks_concurrently(
                remaining_urls,
                interaction.user,
                concurrency=6,
            )
            for t in tracks:
                await state.enqueue(t)

        interaction.client.loop.create_task(_load_rest())
        return

    # Single track / search
    try:
        track = await resolve_track(query, interaction.user)
    except Exception as e:
        await interaction.followup.send(f"Could not load that track: {e}")
        return

    await state.enqueue(track)
    await state.play_next()

    dur = format_duration(track.duration)
    await interaction.followup.send(
        f"Queued: **{track.title}** (`{dur}`)\n{track.webpage_url}"
    )


@tree.command(name="nowplaying", description="Show the currently playing track")
async def nowplaying(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "This only works in a server.", ephemeral=True
        )
        return

    state = get_guild_state(interaction.guild)
    if not state.current:
        await interaction.response.send_message(
            "Nothing is playing right now.", ephemeral=True
        )
        return

    dur = format_duration(state.current.duration)
    await interaction.response.send_message(
        f"Now playing: **{state.current.title}** (`{dur}`)\n{state.current.webpage_url}"
    )


@tree.command(name="queue", description="Show the current queue")
async def queue(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "This only works in a server.", ephemeral=True
        )
        return

    state = get_guild_state(interaction.guild)

    lines: list[str] = []
    if state.current:
        lines.append(
            f"Now: **{state.current.title}** (`{format_duration(state.current.duration)}`)"
        )
    else:
        lines.append("Now: (nothing)")

    upcoming = list(getattr(state.queue, "_queue", []))
    if not upcoming:
        lines.append("Up next: (empty)")
    else:
        lines.append("Up next:")
        for idx, t in enumerate(upcoming[:10], start=1):
            lines.append(f"{idx}. {t.title} (`{format_duration(t.duration)}`)")
        if len(upcoming) > 10:
            lines.append(f"…and {len(upcoming) - 10} more")

    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@tree.command(name="pause", description="Pause playback")
async def pause(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "This only works in a server.", ephemeral=True
        )
        return

    state = get_guild_state(interaction.guild)
    if not state.voice_client or not state.voice_client.is_connected():
        await interaction.response.send_message(
            "I’m not connected to voice.", ephemeral=True
        )
        return

    if state.voice_client.is_playing():
        state.voice_client.pause()
        await interaction.response.send_message("Paused.", ephemeral=True)
        return

    await interaction.response.send_message("Nothing is playing.", ephemeral=True)


@tree.command(name="resume", description="Resume playback")
async def resume(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "This only works in a server.", ephemeral=True
        )
        return

    state = get_guild_state(interaction.guild)
    if not state.voice_client or not state.voice_client.is_connected():
        await interaction.response.send_message(
            "I’m not connected to voice.", ephemeral=True
        )
        return

    if state.voice_client.is_paused():
        state.voice_client.resume()
        await interaction.response.send_message("Resumed.", ephemeral=True)
        return

    await interaction.response.send_message("I’m not paused.", ephemeral=True)


@tree.command(name="skip", description="Skip the current track")
async def skip(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "This only works in a server.", ephemeral=True
        )
        return

    state = get_guild_state(interaction.guild)
    if not state.voice_client or not state.voice_client.is_connected():
        await interaction.response.send_message(
            "I’m not connected to voice.", ephemeral=True
        )
        return

    if state.voice_client.is_playing() or state.voice_client.is_paused():
        state.voice_client.stop()
        await interaction.response.send_message("Skipped.", ephemeral=True)
        return

    await interaction.response.send_message("Nothing to skip.", ephemeral=True)


@tree.command(name="stop", description="Stop playback and clear the queue")
async def stop(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "This only works in a server.", ephemeral=True
        )
        return

    state = get_guild_state(interaction.guild)
    if state.voice_client and state.voice_client.is_connected():
        if state.voice_client.is_playing() or state.voice_client.is_paused():
            state.voice_client.stop()
    await state.clear_queue()
    state.current = None
    await interaction.response.send_message(
        "Stopped and cleared queue.", ephemeral=True
    )


@tree.command(name="leave", description="Disconnect from voice and clear the queue")
async def leave(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message(
            "This only works in a server.", ephemeral=True
        )
        return

    state = get_guild_state(interaction.guild)
    await state.disconnect()
    await interaction.response.send_message("Disconnected.", ephemeral=True)


@tree.command(name="autoplay", description="Enable or disable autoplay mode")
@app_commands.describe(enabled="True to enable autoplay, False to disable")
async def autoplay(interaction: discord.Interaction, enabled: bool):
    if interaction.guild is None:
        await interaction.response.send_message(
            "This only works in a server.", ephemeral=True
        )
        return

    state = get_guild_state(interaction.guild)
    state.set_autoplay(enabled)

    if enabled:
        await interaction.response.send_message(
            "🔁 Autoplay **enabled**. The bot will automatically play related tracks when the queue is empty.",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            "⏹️ Autoplay **disabled**.", ephemeral=True
        )
