import discord
from discord.ext import tasks
from discord import app_commands
import json
import os
from dotenv import load_dotenv
import time


#####################################################################################################
# Load environment variables
# Import constants
from utils.const import SETTINGS_FILE, TOKEN


load_dotenv()

#####################################################################################################
# Load settings data

# Initialize or load settings data
if not os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({}, f)
with open(SETTINGS_FILE, "r") as f:
    settings = json.load(f)


#####################################################################################################
from utils.client import setup_client

client, tree = setup_client()

#####################################################################################################
# Import commands and functions

from utils.birthday import check_birthdays, update_birthdays
from utils.leveling import increase_xp_periodically

from commands.birthday import add_birthday, list_birthdays, test_birthday
from commands.leveling import xp, leaderboard
from commands.setup import app_setup


tree.add_command(app_setup)
tree.add_command(add_birthday)
tree.add_command(list_birthdays)
tree.add_command(test_birthday)
tree.add_command(xp)
tree.add_command(leaderboard)

#####################################################################################################
### Bot events

from utils.data import load_data, save_data


# On member join event: add user entry to data.json
@client.event
async def on_member_join(member):
    data = load_data()
    guild_id = str(member.guild.id)
    user_id = str(member.id)

    # Ensure the guild entry exists
    if guild_id not in data:
        data[guild_id] = {}

    # Add the new user entry with default values
    if user_id not in data[guild_id]:
        data[guild_id][user_id] = {"bdate": "Unknown", "xp": 0}
        save_data(data)  # Save the updated data
        # print(f"Added {member} to the data file.")


# Events to handle message activity

# Global dictionary to track when members last sent a message
member_last_activity = {}


@client.event
async def on_message(message):
    # Ignore messages from bots
    if message.author.bot:
        return

    # Load the existing data
    data = load_data()

    # Ensure the guild exists in the data
    guild_id = str(message.guild.id)
    if guild_id not in data:
        data[guild_id] = {}

    # Ensure the user exists in the guild's data
    user_id = str(message.author.id)
    if user_id not in data[guild_id]:
        data[guild_id][user_id] = {"bdate": "Unknown", "xp": 0}
    else:
        # Ensure "xp" and "bdate" are initialized
        user_data = data[guild_id][user_id]
        if "xp" not in user_data:
            user_data["xp"] = 0
        if "bdate" not in user_data:
            user_data["bdate"] = "Unknown"

    # Ensure the guild exists in `member_last_activity`
    if message.guild.id not in member_last_activity:
        member_last_activity[message.guild.id] = {}

    # Update the member's last activity timestamp
    member_last_activity[message.guild.id][message.author.id] = time.time()

    # Save the updated data
    save_data(data)


@client.event
async def on_ready():
    await tree.sync()  # Sync commands to Discord

    # Display activity : Cooking myself kek
    activity = discord.Activity(
        type=discord.ActivityType.watching, name="Aki suffer 🤣"
    )
    await client.change_presence(status=discord.Status.online, activity=activity)

    # Indicate login status
    print(f"Logged in as {client.user}")

    # Update birthday data (from data channel)
    update_birthdays.start()

    # Check for people birthday daily
    client.loop.create_task(check_birthdays())

    # Xp
    client.loop.create_task(increase_xp_periodically(member_last_activity, client))


client.run(TOKEN)
