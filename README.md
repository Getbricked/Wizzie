# Wizzie Discord Bot

Wizzie is a Discord bot made from discord.py!

## Invite link - [Wizzie](https://discord.com/oauth2/authorize?client_id=1171940876382130206&permissions=8&integration_type=0&scope=bot)

## Features

- **Birthday Data Collect**: Get server members's birthday data from a channel.
- **Birthday Celebrations**: Celebrate birthdays with messages.
- **Birthday Tests**: To test how the bot works.
- **Leveling Sytem**: Leveling up by sending messages in the server!

## Commands (admin only)

### Setup (keep in mind that all birthday in data_channel must have formate dd-mm)

level_flag: default is True if False then level-up system will be disabled
birthday_channel: the channel that server will receive birthday announcement
data_channel: the channel where server can gather user's birthday data (must be format dd-mm)
announcement_channel: the channel where Wizzie will post level up announcement

```
/setup birthday_role: birthday_channel: data_channel: level_flag: announcement_channel:
```

### Add a user's birthday (must have format dd-mm)

```
/add-birthday user: date:
```

### List all birthdays in the server

```
/list-birthdays
```

### Test birthday

```
/test-birthday user:
```

## Commands (everyone)

### XP: get user or other users xp, level info

```
/xp user:
```

### Leaderboard:

```
/leaderboard
```

## Data structure

```json
{
  "guild_id": {
    "user_id": {
      "bdate": "dd-mm",
      "xp": 0
    }
  }
}
```

## Font problem for ubuntu:

```
sudo apt-get install ttf-mscorefonts-installer
```

### Change path to fonts in utils/leveling.py

```python
    # Load fonts (replace with the path to your fonts)
    font_large = ImageFont.truetype(
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf", 24
    )
    font_large_bold = ImageFont.truetype(
        "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf", 24
    )  # Bold version
    font_small = ImageFont.truetype(
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf", 18
    )
```

### For windows:

```python
    # Load fonts (replace with the path to your fonts)
    font_large = ImageFont.truetype("arial.ttf", 24)  # Normal font
    font_large_bold = ImageFont.truetype(
        "arialbd.ttf", 24
    )  # Bold font (use your own bold font)
    font_small = ImageFont.truetype("arial.ttf", 18)
```

### For other linux or distributions:

- Make sure to install the font (you can change it to whatever you want as well)
- Change the path to the font like for Ubuntu
