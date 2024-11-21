# Wizzie Discord Bot

Wizzie is a Discord bot designed to help you manage and celebrate birthdays within your Discord server!

## Features

- **Birthday Data Collect**: Get server members's birthday data from a channel.
- **Birthday Celebrations**: Celebrate birthdays with messages.
- **Birthday Tests**: To test how the bot works.

## Command (admin only)

### Setup

```
/setup birthday_role:<role> announcement_channel:<channel> data_channel:<channel>
```

### Add a user's birthday (must have format dd-mm)

```
/add-birthday user:<user> date:dd-mm
```

### List all birthdays in the server

```
/list-birthdays
```

### Test birthday

```
/test-birthday user:<user>
```