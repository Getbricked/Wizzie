# Music Cache Directory

This directory stores downloaded audio tracks for improved playback quality and reduced lag.

## How it works
- Tracks are downloaded in Opus format (128kbps) optimized for Discord
- Files are named by video ID (e.g., `dQw4w9WgXcQ.opus`)
- Cached tracks play instantly without buffering
- Cache is automatically managed to prevent excessive disk usage

## Cache Management
- Default max age: 7 days
- Default max size: 500 MB
- Old files are automatically cleaned up when limits are exceeded
- You can manually clear the cache by deleting files in this directory

## Benefits
- **Zero buffering** during playback
- **No lag** from network issues
- **Higher quality** audio (consistent bitrate)
- **Instant playback** for repeated songs
- **Reduced bandwidth** usage for frequently played tracks
