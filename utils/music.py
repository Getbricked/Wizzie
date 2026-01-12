from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional

import discord


try:
    import yt_dlp  # type: ignore
except Exception as e:  # pragma: no cover
    yt_dlp = None
    _yt_dlp_import_error = e


@dataclass(frozen=True)
class Track:
    title: str
    stream_url: str
    webpage_url: str
    duration: Optional[int]
    requested_by_id: int


YTDLP_OPTIONS_SINGLE = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}

YTDLP_OPTIONS_PLAYLIST = {
    **YTDLP_OPTIONS_SINGLE,
    "noplaylist": False,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


class GuildMusicState:
    def __init__(self, guild_id: int, loop: asyncio.AbstractEventLoop):
        self.guild_id = guild_id
        self._loop = loop

        self.voice_client: Optional[discord.VoiceClient] = None
        self.queue: asyncio.Queue[Track] = asyncio.Queue()
        self.current: Optional[Track] = None

        self.volume: float = 0.5
        self._advance_lock = asyncio.Lock()

    def is_playing(self) -> bool:
        return bool(
            self.voice_client
            and self.voice_client.is_connected()
            and self.voice_client.is_playing()
        )

    def is_paused(self) -> bool:
        return bool(
            self.voice_client
            and self.voice_client.is_connected()
            and self.voice_client.is_paused()
        )

    async def connect(self, channel: discord.VoiceChannel) -> None:
        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.channel and self.voice_client.channel.id == channel.id:
                return
            await self.voice_client.move_to(channel)
            return

        self.voice_client = await channel.connect()

    async def disconnect(self) -> None:
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect(force=True)
        self.voice_client = None
        self.current = None
        await self.clear_queue()

    async def clear_queue(self) -> None:
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break

    async def enqueue(self, track: Track) -> None:
        await self.queue.put(track)

    async def play_next(self) -> None:
        async with self._advance_lock:
            if not self.voice_client or not self.voice_client.is_connected():
                self.current = None
                return

            if self.voice_client.is_playing() or self.voice_client.is_paused():
                return

            if self.queue.empty():
                self.current = None
                return

            track = await self.queue.get()
            self.current = track

            source = discord.FFmpegPCMAudio(track.stream_url, **FFMPEG_OPTIONS)
            audio = discord.PCMVolumeTransformer(source, volume=self.volume)

            def _after(error: Optional[BaseException]) -> None:
                # Called from a different thread by discord.py
                asyncio.run_coroutine_threadsafe(self._on_track_end(error), self._loop)

            self.voice_client.play(audio, after=_after)

    async def _on_track_end(self, error: Optional[BaseException]) -> None:
        if error:
            # Swallow playback errors; next play will attempt to continue
            pass
        if self.current is not None:
            self.queue.task_done()
        await self.play_next()


_guild_states: Dict[int, GuildMusicState] = {}


def get_guild_state(guild: discord.Guild) -> GuildMusicState:
    state = _guild_states.get(guild.id)
    if state is None:
        state = GuildMusicState(guild.id, asyncio.get_running_loop())
        _guild_states[guild.id] = state
    return state


def _require_yt_dlp() -> None:
    if yt_dlp is None:
        raise RuntimeError(
            "yt-dlp is not installed or failed to import. "
            "Install it with `pip install yt-dlp` and restart the bot. "
            f"Import error: {_yt_dlp_import_error!r}"
        )


async def resolve_track(query_or_url: str, requested_by: discord.abc.User) -> Track:
    _require_yt_dlp()

    def _extract() -> dict:
        with yt_dlp.YoutubeDL(YTDLP_OPTIONS_SINGLE) as ydl:  # type: ignore[attr-defined]
            return ydl.extract_info(query_or_url, download=False)

    info = await asyncio.to_thread(_extract)

    # Handle ytsearch results
    if isinstance(info, dict) and info.get("entries"):
        entry = next((e for e in info["entries"] if e), None)
        if entry is None:
            raise ValueError("No results found")
        info = entry

    if not isinstance(info, dict):
        raise ValueError("Failed to extract media info")

    stream_url = info.get("url")
    title = info.get("title") or "Unknown title"
    webpage_url = info.get("webpage_url") or info.get("original_url") or query_or_url
    duration = info.get("duration")

    if not stream_url:
        raise ValueError("Could not get stream URL from extractor")

    return Track(
        title=str(title),
        stream_url=str(stream_url),
        webpage_url=str(webpage_url),
        duration=int(duration) if isinstance(duration, (int, float)) else None,
        requested_by_id=requested_by.id,
    )


async def resolve_tracks(
    query_or_url: str,
    requested_by: discord.abc.User,
    max_tracks: int = 50,
) -> List[Track]:
    """Resolve a query/URL into one or more playable tracks.

    - If a playlist is provided, this returns all entries as individual Tracks.
    - If a normal URL or search term is provided, this returns a single-element list.
    """

    _require_yt_dlp()

    def _extract_any() -> dict:
        with yt_dlp.YoutubeDL(YTDLP_OPTIONS_PLAYLIST) as ydl:  # type: ignore[attr-defined]
            return ydl.extract_info(query_or_url, download=False)

    info = await asyncio.to_thread(_extract_any)

    if not isinstance(info, dict):
        raise ValueError("Failed to extract media info")

    entries = info.get("entries")
    if entries:
        # Playlist/search. For search, yt-dlp returns entries too; in that case we only want the first.
        if info.get("_type") == "playlist" or info.get("extractor_key") in {
            "YoutubeTab",
            "YoutubePlaylist",
        }:
            raw_entries = [e for e in entries if isinstance(e, dict)]
        else:
            raw_entries = [
                next((e for e in entries if isinstance(e, dict) and e), None)
            ]
            raw_entries = [e for e in raw_entries if e]

        if max_tracks is not None and max_tracks > 0:
            raw_entries = raw_entries[:max_tracks]

        tracks: List[Track] = []
        for entry in raw_entries:
            # Many playlist entries don't include a direct stream URL. Re-extract each entry.
            entry_url = (
                entry.get("webpage_url")
                or entry.get("original_url")
                or entry.get("url")
            )
            if not entry_url:
                continue
            try:
                track = await resolve_track(str(entry_url), requested_by)
                tracks.append(track)
            except Exception:
                # Skip broken/unavailable entries
                continue

        if not tracks:
            raise ValueError("No playable tracks found in playlist")
        return tracks

    # Single item
    track = await resolve_track(query_or_url, requested_by)
    return [track]


def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "Unknown"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
