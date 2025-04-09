from datetime import datetime, timedelta
import asyncio
import json
import os
from discord.ext import tasks
from utils.const import DATA_FILE, CURRENT_TIME, SETTINGS_FILE
import discord
from discord import app_commands
from utils.client import setup_client

# Set up the bot client
# client, tree = setup_client()

# Initialize or load birthday data
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)
with open(DATA_FILE, "r") as f:
    birthdays = json.load(f)
# Initialize or load settings data
if not os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({}, f)
with open(SETTINGS_FILE, "r") as f:
    settings = json.load(f)


#####################################################################################################
# Helper Functions
def save_birthdays():
    """Save the updated birthday data to the file."""
    with open(DATA_FILE, "w") as f:
        json.dump(birthdays, f, indent=4)


def add_or_update_birthday(guild_id, user_id, bdate):
    """Add or update a birthday for a user in the given guild."""
    guild_id = str(guild_id)
    user_id = str(user_id)

    if guild_id not in birthdays:
        birthdays[guild_id] = {}

    birthdays[guild_id][user_id] = {
        "bdate": bdate,
        "xp": birthdays.get(guild_id, {}).get(user_id, {}).get("xp", 0),
    }


def delete_birthday(guild_id, user_id):
    """Delete a birthday for a user in the given guild."""
    guild_id = str(guild_id)
    user_id = str(user_id)

    if guild_id in birthdays and user_id in birthdays[guild_id]:
        del birthdays[guild_id][user_id]
        if not birthdays[
            guild_id
        ]:  # If no more birthdays in the guild, remove the guild entry
            del birthdays[guild_id]
        save_birthdays()
        return True
    return False


def get_updated_guild_birthdays(guild_id):
    """Retrieve all birthdays for a specific guild."""
    with open(DATA_FILE, "r") as f:
        birthdays = json.load(f)
    return birthdays.get(str(guild_id), {})


#####################################################################################################
# Birthday Checker Task
async def check_birthdays(client):
    while True:
        now = datetime.now()
        today = now.strftime("%d-%m")
        print(f"{CURRENT_TIME} - Checking birthdays for {today}.")

        for guild_id, users in birthdays.items():
            guild = client.get_guild(int(guild_id))
            if not guild:
                # print(f"Guild {guild_id} not found.")
                continue

            role_name = settings.get(guild_id, {}).get("birthday_role", "Birthday")
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                # print(f"Role {role_name} not found in guild {guild_id}.")
                continue

            for user_id, data in users.items():
                user = guild.get_member(int(user_id))
                if not user:
                    # print(f"User {user_id} not found in guild {guild_id}.")
                    continue

                if data["bdate"] == today:
                    print(f"Today is {user.name}'s birthday!")
                    if role not in user.roles:
                        try:
                            await user.add_roles(role)
                            print(
                                f"{CURRENT_TIME} - Birthday role assigned to {user.name}."
                            )
                        except discord.Forbidden:
                            continue
                        except discord.HTTPException as e:
                            continue

                        channel_name = settings.get(guild_id, {}).get(
                            "birthday_channel", "general"
                        )
                        channel = discord.utils.get(guild.channels, name=channel_name)
                        if channel:
                            try:
                                await channel.send(
                                    f"🎉 Happy Birthday, {user.mention}! 🎂\n https://tenor.com/view/happy-birthday-bon-anniversaire-birthday-cake-birthday-birthday-fiesta-gif-8599251704042047456"
                                )
                                print(
                                    f"{CURRENT_TIME} - Birthday message sent for {user.name}."
                                )
                            except discord.Forbidden:
                                continue
                            except discord.HTTPException as e:
                                continue
                elif role in user.roles:
                    # print(f"Removing birthday role from {user.name}.")
                    try:
                        await user.remove_roles(role)
                        print(
                            f"{CURRENT_TIME} - Birthday role removed from {user.name}."
                        )
                    except discord.Forbidden:
                        continue
                    except discord.HTTPException as e:
                        continue

        # Wait until the next day
        next_day = now + timedelta(days=1)
        next_update = datetime.combine(next_day, datetime.min.time())
        hours = int(((next_update - now).seconds) / 3600)
        minutes = int(((next_update - now).seconds) / 60) % 60

        if hours != 0 or minutes != 0:
            print(
                f"{CURRENT_TIME} - Next birthday update in {hours} hours and {minutes} minutes."
            )

        await asyncio.sleep((next_update - now).seconds)


#####################################################################################################
# Get birthday data from data channel
@tasks.loop(hours=1)  # This task will run every hour
async def update_birthdays(client):
    try:
        # Load the current birthdays from the file (ensure it has the latest data)
        with open(DATA_FILE, "r") as f:
            birthdays = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("Error reading birthdays file. Initializing empty data.")
        birthdays = {}

    # Iterate through all guilds
    for guild in client.guilds:
        guild_id = str(guild.id)
        data_channel_name = settings.get(guild_id, {}).get("data_channel")

        if not data_channel_name:
            # print(f"Guild {guild_id}: No data channel set.")
            continue  # Skip if there's no data channel set for this guild

        # Fetch the data channel (where users post their birthdays)
        data_channel = discord.utils.get(guild.text_channels, name=data_channel_name)

        if not data_channel:
            # print(f"Guild {guild_id}: Data channel '{data_channel_name}' not found.")
            continue  # Skip if the data channel is not found

        # print(f"Guild {guild_id}: Reading messages from '{data_channel_name}'.")

        # Initialize guild data if not present
        if guild_id not in birthdays:
            birthdays[guild_id] = {}

        # Process messages in the data channel
        async for message in data_channel.history(limit=100):
            # Skip if the message was sent by a bot
            if message.author.bot:
                continue

            content = message.content.strip()
            if not content:
                continue  # Skip empty messages

            try:
                # Validate if the content is a valid birthday (dd-mm format)
                bdate = datetime.strptime(content, "%d-%m").strftime("%d-%m")
                user_id = str(message.author.id)

                # Update the birthdays data for the guild

                birthdays[guild_id][user_id] = {
                    "bdate": bdate,
                    "xp": birthdays.get(guild_id, {}).get(user_id, {}).get("xp", 0),
                }
                print(
                    f"Added birthday for user {message.author.name} in guild {guild.name}: {bdate}"
                )

            except ValueError:
                # print(f"Invalid bdate format in message: {content}")
                continue  # Skip invalid bdate formats

    # Save the updated birthdays data to the file
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(birthdays, f, indent=4)
        # print(f"{datetime.now().strftime('%H:%M')} - Updated birthdays file.")
    except IOError as e:
        print(f"Error writing to birthdays file: {e}")


def get_zodiac(day: int, month: int) -> str:
    zodiac_signs = [
        ("♑   Capricorn", (1, 20)),
        ("♒   Aquarius", (2, 19)),
        ("♓   Pisces", (3, 20)),
        ("♈   Aries", (4, 20)),
        ("♉   Taurus", (5, 20)),
        ("♊   Gemini", (6, 20)),
        ("♋   Cancer", (7, 22)),
        ("♌   Leo", (8, 22)),
        ("♍   Virgo", (9, 22)),
        ("♎   Libra", (10, 22)),
        ("♏   Scorpio", (11, 21)),
        ("♐   Sagittarius", (12, 21)),
        ("♑   Capricorn", (12, 31)),
    ]
    for sign, (m, d) in zodiac_signs:
        if (month < m) or (month == m and day <= d):
            return sign
