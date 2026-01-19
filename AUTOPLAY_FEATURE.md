# Autoplay Feature

## Overview
The autoplay feature automatically queues and plays related tracks when your queue becomes empty, keeping the music going without manual intervention.

## Usage

### Enable Autoplay
```
/autoplay enabled:True
```

### Disable Autoplay
```
/autoplay enabled:False
```

## How It Works

1. **When queue is empty**: Instead of stopping, the bot automatically finds and plays a related track
2. **Smart selection**: Uses YouTube's related videos algorithm to find similar content
3. **No repeats**: Tracks recently played via autoplay won't be repeated (maintains 50-track history)
4. **Seamless experience**: Works with the existing caching and preloading system for smooth playback

## Example Flow

1. User plays a song: `/play never gonna give you up`
2. Song finishes playing
3. Queue is empty
4. **If autoplay is enabled**: Bot automatically queues and plays a related Rick Astley song
5. Process repeats indefinitely until autoplay is disabled or user stops playback

## Technical Details

- Related tracks are fetched from YouTube's related videos API
- Fallback to search-based recommendations if API fails
- Autoplay tracks are cached just like manually requested tracks
- History is cleared when autoplay is disabled
- Works with all existing music commands (`/skip`, `/pause`, `/stop`, etc.)

## Notes

- Autoplay state is per-guild (server)
- History is kept in memory (resets on bot restart)
- Failed autoplay attempts are silent (won't spam errors)
- You can still manually queue tracks while autoplay is enabled
