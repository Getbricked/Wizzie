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
    stream_url: str
    webpage_url: str
    duration: Optional[int]
    requested_by_id: int
    video_id: Optional[str] = None
    cached_file: Optional[str] = None


# Cache directory for downloaded tracks
CACHE_DIR = Path("cache/music")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

YTDLP_OPTIONS_SINGLE = {
    "format": "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "outtmpl": str(CACHE_DIR / "%(id)s.%(ext)s"),
    "keepvideo": False,
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "opus",
            "preferredquality": "128",
        }
    ],
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
        "-probesize 10M -analyzeduration 10M"
    ),
    "options": "-vn -bufsize 512k",
}

FFMPEG_OPTIONS_CACHED = {
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
        self._preload_task: Optional[asyncio.Task] = None
        self.autoplay_enabled: bool = False
        self._autoplay_history: List[str] = []  # Track video IDs to avoid repeats

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
                # Try autoplay if enabled
                if self.autoplay_enabled and self.current:
                    await self._queue_autoplay_track()
                    if self.queue.empty():
                        self.current = None
                        return
                else:
                    self.current = None
                    return

            track = await self.queue.get()
            self.current = track

            # Use cached file if available, otherwise stream
            if track.cached_file and os.path.exists(track.cached_file):
                source = discord.FFmpegOpusAudio(
                    track.cached_file, **FFMPEG_OPTIONS_CACHED
                )
            else:
                source = discord.FFmpegPCMAudio(track.stream_url, **FFMPEG_OPTIONS)

            audio = discord.PCMVolumeTransformer(source, volume=self.volume)

            def _after(error: Optional[BaseException]) -> None:
                # Called from a different thread by discord.py
                asyncio.run_coroutine_threadsafe(self._on_track_end(error), self._loop)

            self.voice_client.play(audio, after=_after)

            # Preload next track in background
            self._start_preload()

    async def _on_track_end(self, error: Optional[BaseException]) -> None:
        if error:
            # Swallow playback errors; next play will attempt to continue
            pass
        if self.current is not None:
            self.queue.task_done()
        await self.play_next()

    def _start_preload(self) -> None:
        """Start preloading the next track in queue."""
        if self._preload_task and not self._preload_task.done():
            return

        if self.queue.empty():
            return

        # Peek at next track without removing it
        try:
            next_track = list(self.queue._queue)[0]
            if next_track and not next_track.cached_file:
                self._preload_task = asyncio.create_task(
                    self._preload_track(next_track)
                )
        except (IndexError, AttributeError):
            pass

    async def _preload_track(self, track: Track) -> None:
        """Download and cache a track in the background."""
        try:
            if track.video_id:
                cached_path = await download_track(track.video_id)
                # Update track in queue (note: this is a best-effort update)
                # The track is immutable, but we'll have the cached file ready
        except Exception:
            # Preload failures are silent
            pass

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
            # Get related tracks from YouTube
            related_track = await get_related_track(
                self.current.video_id,
                exclude_ids=self._autoplay_history,
                requested_by_id=self.current.requested_by_id,
            )

            if related_track:
                await self.enqueue(related_track)
                # Keep history limited to prevent memory growth
                self._autoplay_history.append(related_track.video_id or "")
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


async def get_related_track(
    video_id: str,
    exclude_ids: List[str],
    requested_by_id: int,
) -> Optional[Track]:
    """Get a related track for autoplay based on the current video."""
    _require_yt_dlp()

    def _extract_related() -> Optional[dict]:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "playlist_items": "1",
        }

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[attr-defined]
                # Get video info which includes related videos
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )

                if not isinstance(info, dict):
                    return None

                # Try to find related videos in various possible fields
                related = []

                # YouTube may provide related videos in different fields
                if "entries" in info:
                    related = info["entries"]
                elif "related_videos" in info:
                    related = info["related_videos"]

                # Filter out already played tracks
                for item in related:
                    if not isinstance(item, dict):
                        continue

                    item_id = item.get("id") or item.get("video_id")
                    if item_id and item_id not in exclude_ids and item_id != video_id:
                        return item

                return None
        except Exception:
            return None

    related_info = await asyncio.to_thread(_extract_related)

    if not related_info:
        # Fallback: search for similar content
        try:
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:  # type: ignore[attr-defined]
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )
                if isinstance(info, dict):
                    title = info.get("title", "")
                    # Search for similar content
                    search_query = f"ytsearch1:{title}"
                    return await resolve_track(
                        search_query, discord.Object(id=requested_by_id), download=True
                    )  # type: ignore
        except Exception:
            pass
        return None

    # Extract the related video ID
    related_id = related_info.get("id") or related_info.get("video_id")
    if not related_id:
        return None

    # Resolve the related track
    try:
        url = f"https://www.youtube.com/watch?v={related_id}"
        return await resolve_track(url, discord.Object(id=requested_by_id), download=True)  # type: ignore
    except Exception:
        return None


async def download_track(video_id: str) -> Optional[str]:
    """Download and cache a track, returning the path to cached file."""
    _require_yt_dlp()

    # Check if already cached
    cached_opus = CACHE_DIR / f"{video_id}.opus"
    if cached_opus.exists():
        return str(cached_opus)

    # Also check for other formats
    for ext in ["webm", "m4a", "mp3"]:
        cached_file = CACHE_DIR / f"{video_id}.{ext}"
        if cached_file.exists():
            return str(cached_file)

    # Download the track
    def _download() -> Optional[str]:
        opts = YTDLP_OPTIONS_SINGLE.copy()
        opts["outtmpl"] = str(CACHE_DIR / f"{video_id}.%(ext)s")

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore[attr-defined]
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

            # Check what file was created
            if cached_opus.exists():
                return str(cached_opus)
            for ext in ["webm", "m4a", "mp3", "ogg"]:
                cached_file = CACHE_DIR / f"{video_id}.{ext}"
                if cached_file.exists():
                    return str(cached_file)
            return None
        except Exception:
            return None

    return await asyncio.to_thread(_download)


async def resolve_track(
    query_or_url: str, requested_by: discord.abc.User, download: bool = True
) -> Track:
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
    video_id = info.get("id")

    if not stream_url:
        raise ValueError("Could not get stream URL from extractor")

    # Try to download and cache the track
    cached_file = None
    if download and video_id:
        cached_file = await download_track(str(video_id))

    return Track(
        title=str(title),
        stream_url=str(stream_url),
        webpage_url=str(webpage_url),
        duration=int(duration) if isinstance(duration, (int, float)) else None,
        requested_by_id=requested_by.id,
        video_id=str(video_id) if video_id else None,
        cached_file=cached_file,
    )


async def resolve_tracks(
    query_or_url: str,
    requested_by: discord.abc.User,
    max_tracks: int = 50,
    download: bool = True,
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
                track = await resolve_track(
                    str(entry_url), requested_by, download=download
                )
                tracks.append(track)
            except Exception:
                # Skip broken/unavailable entries
                continue

        if not tracks:
            raise ValueError("No playable tracks found in playlist")
        return tracks

    # Single item
    track = await resolve_track(query_or_url, requested_by, download=download)
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
    download: bool = True,  # Default False for background loading
) -> List[Track]:
    """Resolve multiple URLs concurrently into streamable Tracks."""
    if not urls:
        return []

    semaphore = asyncio.Semaphore(max(1, int(concurrency)))

    async def _worker(url: str) -> Optional[Track]:
        async with semaphore:
            try:
                return await resolve_track(url, requested_by, download=download)
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


def get_cache_size() -> Tuple[int, int]:
    """Get cache size in bytes and number of files."""
    total_size = 0
    file_count = 0

    if not CACHE_DIR.exists():
        return 0, 0

    for file in CACHE_DIR.iterdir():
        if file.is_file():
            total_size += file.stat().st_size
            file_count += 1

    return total_size, file_count


async def cleanup_cache(max_age_days: int = 7, max_size_mb: int = 500) -> int:
    """Clean up old cached files. Returns number of files deleted."""
    import time

    if not CACHE_DIR.exists():
        return 0

    deleted = 0
    current_time = time.time()
    max_age_seconds = max_age_days * 24 * 60 * 60
    max_size_bytes = max_size_mb * 1024 * 1024

    # Get all files with their modification times
    files_with_time = []
    for file in CACHE_DIR.iterdir():
        if file.is_file():
            files_with_time.append((file, file.stat().st_mtime))

    # Sort by modification time (oldest first)
    files_with_time.sort(key=lambda x: x[1])

    # Delete old files
    for file, mtime in files_with_time:
        age = current_time - mtime
        if age > max_age_seconds:
            try:
                file.unlink()
                deleted += 1
            except Exception:
                pass

    # Check total size and delete oldest files if needed
    total_size, _ = get_cache_size()
    if total_size > max_size_bytes:
        # Refresh file list after age-based deletion
        files_with_time = []
        for file in CACHE_DIR.iterdir():
            if file.is_file():
                files_with_time.append(
                    (file, file.stat().st_mtime, file.stat().st_size)
                )

        files_with_time.sort(key=lambda x: x[1])  # Oldest first

        current_size = total_size
        for file, mtime, size in files_with_time:
            if current_size <= max_size_bytes:
                break
            try:
                file.unlink()
                current_size -= size
                deleted += 1
            except Exception:
                pass

    return deleted
