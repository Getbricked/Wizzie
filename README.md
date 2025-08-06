# Wizzie Discord Bot

<p align="center">
  <img src="Snowy-Wizzie.gif" alt="">
</p>

## Invite link - [Wizzie](https://discord.com/oauth2/authorize?client_id=1171940876382130206&permissions=8&integration_type=0&scope=bot)

## Features

- **Birthday Data Collect**: Get server members's birthday data from a channel.
- **Birthday Celebrations**: Celebrate birthdays with messages.
- **Birthday Tests**: To test how the bot works.
- **Leveling Sytem**: Leveling up by sending messages in the server!

## Commands (admin only)

### Setup (keep in mind that all birthday in data_channel must have formate dd-mm)

**<span style="color:red">YOU SHOULD RUN THIS COMMAND AFTER YOU INVITE WIZZIE</span>**

- level_flag: default is True if False then level-up system will be disabled
- birthday_channel: the channel that server will receive birthday announcement
- data_channel: the channel where server can gather user's birthday data (must be format dd-mm)
- announcement_channel: the channel where Wizzie will post level up announcement

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

### Disable or Enable xp on a channel:

```
/disable-xp channel:
```

```
/enable-xp channel:
```

### Clear chat:

- amount (optional): default amount is 10 if there's no input

```
/clear amount:
```

#### Basically recreate the channel (delete all messages)

```
/clear-all
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
