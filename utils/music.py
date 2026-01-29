from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import discord


try:
    import yt_dlp  # type: ignore
except Exception as e:  # pragma: no cover
    yt_dlp = None
    _yt_dlp_import_error = e


@dataclass(frozen=True)
class Track:
    title: str
    webpage_url: str
    duration: Optional[int]
    requested_by_id: int
    video_id: Optional[str] = None
    stream_url: Optional[str] = (
        None  # Can be None, will be fetched fresh before playing
    )


YTDLP_OPTIONS_SINGLE = {
    "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    # Additional options to avoid 403 errors
    "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    },
}

YTDLP_OPTIONS_PLAYLIST = {
    **YTDLP_OPTIONS_SINGLE,
    "noplaylist": False,
}

YTDLP_OPTIONS_PLAYLIST_FLAT = {
    **YTDLP_OPTIONS_SINGLE,
    "noplaylist": False,
    # Much faster: returns entries without resolving each into stream URLs.
    "extract_flat": "in_playlist",
}

FFMPEG_OPTIONS = {
    "before_options": (
        "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
        "-probesize 10M -analyzeduration 10M "
        '-user_agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"'
    ),
    "options": "-vn -bufsize 512k",
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
        self.autoplay_enabled: bool = False
        self._autoplay_history: List[str] = []  # Track video IDs to avoid repeats
        self.text_channel: Optional[discord.TextChannel] = (
            None  # For now playing messages
        )
        self._idle_disconnect_task: Optional[asyncio.Task] = None
        self._idle_timeout: int = 300  # 5 minutes of inactivity

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

    def _is_voice_connected(self) -> bool:
        """Check if voice client is valid and connected."""
        return bool(
            self.voice_client
            and self.voice_client.is_connected()
            and hasattr(self.voice_client, "ws")
            and self.voice_client.ws is not None
        )

    async def connect(self, channel: discord.VoiceChannel) -> None:
        if self.voice_client and self.voice_client.is_connected():
            if self.voice_client.channel and self.voice_client.channel.id == channel.id:
                return
            await self.voice_client.move_to(channel)
            return

        self.voice_client = await channel.connect()

    async def disconnect(self) -> None:
        # Cancel idle disconnect task
        if self._idle_disconnect_task and not self._idle_disconnect_task.done():
            self._idle_disconnect_task.cancel()
            self._idle_disconnect_task = None

        if self.voice_client:
            try:
                # Clear voice channel status
                if self.voice_client.channel:
                    try:
                        await self.voice_client.channel.edit(status=None)
                    except Exception:
                        pass
                if self.voice_client.is_connected():
                    await self.voice_client.disconnect(force=True)
            except Exception:
                pass  # Ignore disconnect errors

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

    def set_text_channel(self, channel: discord.TextChannel) -> None:
        """Set the text channel for now playing messages."""
        self.text_channel = channel

    async def send_now_playing(self, track: Track, is_autoplay: bool = False) -> None:
        """Send a now playing message to the text channel."""
        if not self.text_channel:
            print(f"DEBUG: No text channel set for sending now playing message")
            return

        try:
            embed = discord.Embed(
                title=(
                    "🎵 Now Playing" if not is_autoplay else "🎵 Now Playing (Autoplay)"
                ),
                description=f"**[{track.title}]({track.webpage_url})**",
                color=(
                    discord.Color.blue() if not is_autoplay else discord.Color.green()
                ),
            )

            if track.duration:
                embed.add_field(
                    name="Duration", value=format_duration(track.duration), inline=True
                )

            requested_by = self.text_channel.guild.get_member(track.requested_by_id)
            if requested_by:
                embed.add_field(
                    name="Requested by", value=requested_by.mention, inline=True
                )

            print(f"DEBUG: Sending now playing to channel {self.text_channel.name}")
            await self.text_channel.send(embed=embed)
        except Exception as e:
            # Log the error for debugging
            print(f"Failed to send now playing message: {e}")

    def _cancel_idle_disconnect(self) -> None:
        """Cancel any pending idle disconnect."""
        if self._idle_disconnect_task and not self._idle_disconnect_task.done():
            self._idle_disconnect_task.cancel()
            self._idle_disconnect_task = None

    async def _idle_disconnect_timer(self) -> None:
        """Disconnect after idle timeout if not in autoplay mode."""
        try:
            await asyncio.sleep(self._idle_timeout)
            # Only disconnect if not in autoplay mode and nothing is playing
            if (
                not self.autoplay_enabled
                and not self.is_playing()
                and self.queue.empty()
            ):
                await self.disconnect()
        except asyncio.CancelledError:
            pass  # Task was cancelled, which is expected

    def _schedule_idle_disconnect(self) -> None:
        """Schedule an idle disconnect if not in autoplay mode."""
        self._cancel_idle_disconnect()
        if not self.autoplay_enabled:
            self._idle_disconnect_task = asyncio.create_task(
                self._idle_disconnect_timer()
            )

    async def play_next(self) -> None:
        async with self._advance_lock:
            # Cancel any idle disconnect since we're about to play
            self._cancel_idle_disconnect()

            # Validate voice connection
            if not self._is_voice_connected():
                self.current = None
                await self.disconnect()
                return

            if self.voice_client.is_playing() or self.voice_client.is_paused():
                return

            if self.queue.empty():
                # Try autoplay if enabled
                if self.autoplay_enabled and self.current:
                    await self._queue_autoplay_track()
                    if self.queue.empty():
                        self.current = None
                        # Schedule idle disconnect for non-autoplay
                        self._schedule_idle_disconnect()
                        return
                else:
                    self.current = None
                    # Schedule idle disconnect when queue is empty
                    self._schedule_idle_disconnect()
                    return

            track = await self.queue.get()
            self.current = track
            is_autoplay = (
                track.video_id in self._autoplay_history if track.video_id else False
            )

            # Get fresh stream URL (YouTube URLs expire)
            try:
                stream_url = await get_fresh_stream_url(track)
            except Exception as e:
                # If we can't get stream URL, skip this track
                if self.current is not None:
                    self.queue.task_done()
                await self.play_next()
                return

            # Validate connection again before playing
            if not self._is_voice_connected():
                if self.current is not None:
                    self.queue.task_done()
                self.current = None
                await self.disconnect()
                return

            try:
                # Stream the track
                source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
                audio = discord.PCMVolumeTransformer(source, volume=self.volume)

                def _after(error: Optional[BaseException]) -> None:
                    # Called from a different thread by discord.py
                    asyncio.run_coroutine_threadsafe(
                        self._on_track_end(error), self._loop
                    )

                self.voice_client.play(audio, after=_after)

                # Set voice channel status to song name
                if self.voice_client.channel:
                    try:
                        # Truncate to 500 chars (Discord limit)
                        status_text = (
                            track.title[:500] if len(track.title) > 500 else track.title
                        )
                        await self.voice_client.channel.edit(status=status_text)
                    except Exception:
                        pass  # Ignore if we can't set status

                # Send now playing message
                await self.send_now_playing(track, is_autoplay=is_autoplay)
            except Exception as e:
                # Handle playback errors (e.g., connection issues)
                if self.current is not None:
                    self.queue.task_done()
                # Try to continue with next track
                await self.play_next()

    async def _on_track_end(self, error: Optional[BaseException]) -> None:
        if error:
            # Log connection errors but continue
            if isinstance(error, (discord.errors.ConnectionClosed, ConnectionError)):
                # Connection was lost, try to recover
                if not self._is_voice_connected():
                    self.current = None
                    await self.disconnect()
                    return

        if self.current is not None:
            self.queue.task_done()

        try:
            await self.play_next()
        except Exception:
            # If play_next fails completely, clean up
            self.current = None
            self._schedule_idle_disconnect()

    def set_autoplay(self, enabled: bool) -> bool:
        """Enable or disable autoplay mode. Returns the new state."""
        self.autoplay_enabled = enabled
        if not enabled:
            self._autoplay_history.clear()
        return self.autoplay_enabled

    async def _queue_autoplay_track(self) -> None:
        """Queue a related track based on current track (autoplay)."""
        if not self.current or not self.current.video_id:
            return

        try:
            # Add current track to history BEFORE finding related tracks
            # to avoid getting the same recommendations repeatedly
            if self.current.video_id not in self._autoplay_history:
                self._autoplay_history.append(self.current.video_id)
                if len(self._autoplay_history) > 50:
                    self._autoplay_history = self._autoplay_history[-50:]

            # Get next track from YouTube's radio/automix API
            related_track = await get_radio_track(
                self.current.video_id,
                exclude_ids=self._autoplay_history,
                requested_by_id=self.current.requested_by_id,
            )

            if related_track:
                await self.enqueue(related_track)
                # Add the related track to history as well
                if (
                    related_track.video_id
                    and related_track.video_id not in self._autoplay_history
                ):
                    self._autoplay_history.append(related_track.video_id)
                    if len(self._autoplay_history) > 50:
                        self._autoplay_history = self._autoplay_history[-50:]
        except Exception:
            # Autoplay failures are silent
            pass


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


async def get_fresh_stream_url(track: Track) -> str:
    """Get a fresh stream URL for a track. YouTube URLs expire, so we fetch them just before playing."""
    _require_yt_dlp()

    # Use video_id if available for faster lookup, otherwise use webpage_url
    url = (
        f"https://www.youtube.com/watch?v={track.video_id}"
        if track.video_id
        else track.webpage_url
    )

    def _extract() -> dict:
        with yt_dlp.YoutubeDL(YTDLP_OPTIONS_SINGLE) as ydl:  # type: ignore[attr-defined]
            return ydl.extract_info(url, download=False)

    info = await asyncio.to_thread(_extract)

    if not isinstance(info, dict):
        raise ValueError("Failed to extract media info")

    stream_url = info.get("url")
    if not stream_url:
        raise ValueError("Could not get stream URL from extractor")

    return str(stream_url)


async def get_radio_track(
    video_id: str,
    exclude_ids: List[str],
    requested_by_id: int,
) -> Optional[Track]:
    """Get next track from YouTube's radio/automix API for autoplay."""
    _require_yt_dlp()

    def _extract_radio_tracks() -> List[dict]:
        """Extract tracks from YouTube's radio playlist."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "playlistend": 10,  # Get first 10 tracks from radio
        }

        try:
            # Use YouTube's radio playlist format: RDAMVM{video_id}
            radio_url = (
                f"https://www.youtube.com/watch?v={video_id}&list=RDAMVM{video_id}"
            )

            with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[attr-defined]
                info = ydl.extract_info(radio_url, download=False)

                if not isinstance(info, dict):
                    return []

                # Get playlist entries
                entries = info.get("entries", [])
                if not entries:
                    return []

                # Return all entries as a list
                return [e for e in entries if isinstance(e, dict)]
        except Exception:
            return []

    radio_tracks = await asyncio.to_thread(_extract_radio_tracks)

    if not radio_tracks:
        return None

    # Find first track that hasn't been played yet
    for track_info in radio_tracks:
        track_id = track_info.get("id") or track_info.get("url")

        # Skip if no ID or already played
        if not track_id or track_id in exclude_ids:
            continue

        # Found a new track, resolve it fully
        try:
            url = track_info.get("url") or f"https://www.youtube.com/watch?v={track_id}"
            return await resolve_track(url, discord.Object(id=requested_by_id))  # type: ignore
        except Exception:
            # If this track fails, continue to next one
            continue

    return None


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

    title = info.get("title") or "Unknown title"
    webpage_url = info.get("webpage_url") or info.get("original_url") or query_or_url
    duration = info.get("duration")
    video_id = info.get("id")

    # We don't store stream_url anymore - it will be fetched fresh before playing
    # This avoids 403 errors from expired URLs

    return Track(
        title=str(title),
        webpage_url=str(webpage_url),
        duration=int(duration) if isinstance(duration, (int, float)) else None,
        requested_by_id=requested_by.id,
        video_id=str(video_id) if video_id else None,
        stream_url=None,  # Will be fetched fresh before playing
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


async def extract_playlist_entry_urls(
    query_or_url: str,
    max_tracks: int = 50,
) -> Tuple[bool, List[str], Optional[str]]:
    """Fast path to detect playlists and extract per-entry URLs.

    Returns (is_playlist, entry_urls, playlist_title).
    For non-playlists, returns (False, [], None).
    """

    _require_yt_dlp()

    def _extract_flat() -> dict:
        with yt_dlp.YoutubeDL(YTDLP_OPTIONS_PLAYLIST_FLAT) as ydl:  # type: ignore[attr-defined]
            return ydl.extract_info(query_or_url, download=False)

    info = await asyncio.to_thread(_extract_flat)
    if not isinstance(info, dict):
        return False, [], None

    entries = info.get("entries")
    if not entries:
        return False, [], None

    is_playlist = info.get("_type") == "playlist"
    title = info.get("title") if is_playlist else None

    urls: List[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_url = (
            entry.get("url") or entry.get("webpage_url") or entry.get("original_url")
        )
        if not entry_url:
            continue
        # For flat extraction, YouTube entries often look like "VIDEO_ID"; prefer full URL if available.
        if isinstance(entry_url, str) and entry_url.startswith("http"):
            urls.append(entry_url)
        else:
            # Best-effort YouTube reconstruction
            urls.append(f"https://www.youtube.com/watch?v={entry_url}")
        if max_tracks and len(urls) >= max_tracks:
            break

    if not is_playlist:
        # Probably a search result list; treat as non-playlist.
        return False, [], None

    return True, urls, str(title) if title else None


async def resolve_tracks_concurrently(
    urls: List[str],
    requested_by: discord.abc.User,
    concurrency: int = 6,
) -> List[Track]:
    """Resolve multiple URLs concurrently into streamable Tracks."""
    if not urls:
        return []

    semaphore = asyncio.Semaphore(max(1, int(concurrency)))

    async def _worker(url: str) -> Optional[Track]:
        async with semaphore:
            try:
                return await resolve_track(url, requested_by)
            except Exception:
                return None

    results = await asyncio.gather(*(_worker(u) for u in urls))
    return [t for t in results if t is not None]


def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "Unknown"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
