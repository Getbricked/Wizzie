# Wizzie Discord Bot

Wizzie is a Discord bot designed to help you manage and celebrate birthdays within your Discord server!

## Features

- **Birthday Data Collect**: Get server members's birthday data from a channel.
- **Birthday Celebrations**: Celebrate birthdays with messages.
- **Birthday Tests**: To test how the bot works.

## Command (admin only)

### Setup (keep in mind that all birthday in data_channel must have formate dd-mm)

```
/setup birthday_role: announcement_channel: data_channel:
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
