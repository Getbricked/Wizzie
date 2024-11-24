import discord
from discord.ext import tasks
from discord import app_commands
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta
import time
import random


# Static parameters
TOKEN_FILE = "token.json"
DATA_FILE = "data.json"
CURRENT_TIME = datetime.now().strftime("%H:%M")

# Load Token
if not os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "w") as f:
        json.dump({}, f)
with open("token.json", "r") as f:
    TOKEN = json.load(f)["token"]

# Load environment variables
load_dotenv()

#####################################################################################################
# Initialize or load birthday data

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)
with open(DATA_FILE, "r") as f:
    birthdays = json.load(f)

# Initialize or load settings data
settings_file = "settings.json"
if not os.path.exists(settings_file):
    with open(settings_file, "w") as f:
        json.dump({}, f)
with open(settings_file, "r") as f:
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

    birthdays[guild_id][user_id] = {"bdate": bdate}


def get_updated_guild_birthdays(guild_id):
    """Retrieve all birthdays for a specific guild."""
    with open(DATA_FILE, "r") as f:
        birthdays = json.load(f)
    return birthdays.get(str(guild_id), {})


#####################################################################################################
# Set up the bot client
intents = discord.Intents.default()
intents.members = True  # Needed to access member details
intents.messages = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


#####################################################################################################
# Birthday Checker Task
async def check_birthdays():
    while True:
        now = datetime.now()
        today = now.strftime("%d-%m")

        for guild_id, users in birthdays.items():
            guild = client.get_guild(int(guild_id))
            if not guild:
                continue

            role_name = settings.get(guild_id, {}).get("birthday_role", "Birthday")
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                continue

            for user_id, data in users.items():
                user = guild.get_member(int(user_id))
                if not user:
                    continue

                if data["bdate"] == today:
                    if role not in user.roles:
                        await user.add_roles(role)
                        channel_name = settings.get(guild_id, {}).get(
                            "birthday_channel", "general"
                        )
                        channel = discord.utils.get(guild.channels, name=channel_name)
                        if channel:
                            await channel.send(f"🎉 Happy Birthday, {user.mention}! 🎂")
                elif role in user.roles:
                    await user.remove_roles(role)

        # Wait until the next day
        next_day = now + timedelta(days=1)
        next_update = datetime.combine(next_day, datetime.min.time())
        hours = int(((next_update - now).seconds) / 3600)
        minutes = int(((next_update - now).seconds) / 60) % 60
        print(
            f"{CURRENT_TIME} - Next birthday update in {hours} hours and {minutes} minutes."
        )
        await asyncio.sleep((next_update - now).seconds)


#####################################################################################################
# Get birthday data from data channel
@tasks.loop(hours=1)  # This task will run every hour
async def update_birthdays():
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
            print(f"Guild {guild_id}: No data channel set.")
            continue  # Skip if there's no data channel set for this guild

        # Fetch the data channel (where users post their birthdays)
        data_channel = discord.utils.get(guild.text_channels, name=data_channel_name)

        if not data_channel:
            print(f"Guild {guild_id}: Data channel '{data_channel_name}' not found.")
            continue  # Skip if the data channel is not found

        print(f"Guild {guild_id}: Reading messages from '{data_channel_name}'.")

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
                if user_id not in birthdays[guild_id]:
                    birthdays[guild_id][user_id] = {"bdate": bdate}
                    print(
                        f"Added birthday for user {message.author.name} in guild {guild.name}: {bdate}"
                    )
                else:
                    print(
                        f"Skipped duplicate birthday for {message.author.name} in guild {guild.name}."
                    )

            except ValueError:
                # print(f"Invalid bdate format in message: {content}")
                continue  # Skip invalid bdate formats

    # Save the updated birthdays data to the file
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(birthdays, f, indent=4)
        print(f"{datetime.now().strftime('%H:%M')} - Updated birthdays file.")
    except IOError as e:
        print(f"Error writing to birthdays file: {e}")


#####################################################################################################
# Slash Command to Add a Birthday
@tree.command(
    name="add-birthday", description="Add a birthday for a user (Admins only)"
)
@app_commands.describe(
    user="The user to add a birthday for", bdate="The user's birthday in DD-MM format"
)
async def add_birthday(
    interaction: discord.Interaction, user: discord.Member, bdate: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need to be an administrator to use this command.", ephemeral=True
        )
        return

    try:
        datetime.strptime(bdate, "%d-%m")  # Validate bdate format
    except ValueError:
        await interaction.response.send_message(
            "Invalid bdate format. Use DD-MM.", ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    add_or_update_birthday(guild_id, user.id, bdate)
    save_birthdays()

    await interaction.response.send_message(
        f"Added birthday for {user.name} on {bdate}!"
    )


#####################################################################################################
# Command to setup the birthday role, announcement channel, and data collection channel
@tree.command(
    name="setup",
    description="Set the birthday role, announcement channel, and data collection channel (Admins only)",
)
@app_commands.describe(
    birthday_role="The role to assign for birthdays",
    announcement_channel="The channel for birthday announcements",
    data_channel="The channel for collecting birthday data",
)
async def app_setup(
    interaction: discord.Interaction,
    birthday_role: discord.Role,
    announcement_channel: discord.TextChannel,
    data_channel: discord.TextChannel,
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need to be an administrator to use this command.", ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    if guild_id not in settings:
        settings[guild_id] = {}

    # Set birthday role, announcement channel, and data channel
    settings[guild_id]["birthday_role"] = birthday_role.name
    settings[guild_id]["birthday_channel"] = announcement_channel.name
    settings[guild_id]["data_channel"] = data_channel.name

    # Save settings to the file
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=4)

    await interaction.response.send_message(
        f"Birthday role set to `{birthday_role.name}`, birthday announcement channel set to `{announcement_channel.name}`, and data collection channel set to `{data_channel.name}`!"
    )


#####################################################################################################
# Test command to check the birthday feature for a specific user
@tree.command(
    name="test-birthday",
    description="Test the birthday feature for a specific user (Admins only)",
)
@app_commands.describe(user="The user to test the birthday feature on")
async def test_birthday(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need to be an administrator to use this command.", ephemeral=True
        )
        return

    guild = interaction.guild
    if not guild:
        await interaction.response.send_message(
            "This command must be used in a server.", ephemeral=True
        )
        return

    # Get birthday role
    role_name = settings.get(str(guild.id), {}).get("birthday_role", "Birthday")
    role = discord.utils.get(guild.roles, name=role_name)

    if not role:
        await interaction.response.send_message(
            "No birthday role is set. Please configure it using `/setup`.",
            ephemeral=True,
        )
        return

    # Assign the role temporarily
    if role in user.roles:
        await interaction.response.send_message(
            f"{user.display_name} already has the role `{role.name}`.", ephemeral=True
        )
        return

    await user.add_roles(role)
    await interaction.response.send_message(
        f"Assigned the role `{role.name}` to {user.name} for testing.",
        ephemeral=True,
    )

    # Send a test message to the birthday channel
    channel_name = settings.get(str(guild.id), {}).get("birthday_channel", "general")
    channel = discord.utils.get(guild.channels, name=channel_name)

    if channel:
        await channel.send(f"🎉 (Test) Happy Birthday, {user.mention}! 🎂")
    else:
        await interaction.followup.send(
            "No birthday announcement channel is set. Please configure it using `/setup`.",
            ephemeral=True,
        )

    # Wait for 30 seconds and then remove the role
    await asyncio.sleep(30)
    await user.remove_roles(role)
    await interaction.followup.send(
        f"Removed the role `{role.name}` from {user.name}. Test completed.",
        ephemeral=True,
    )


#####################################################################################################
# Slash Command to List Birthdays (Admins only)
@tree.command(
    name="list-birthdays", description="List all birthdays in the server (Admins only)."
)
async def list_birthdays(interaction: discord.Interaction):
    # Check if the user has administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need to be an administrator to use this command.", ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)

    # Check if the guild has any birthdays recorded
    guild_birthdays = get_updated_guild_birthdays(guild_id)
    if not guild_birthdays:
        await interaction.response.send_message(
            "No birthdays found for this server.", ephemeral=True
        )
        return

    # Format the list of birthdays
    response = "**🎂 Birthdays in this server:**\n"
    for user_id, data in guild_birthdays.items():

        # Skip users with bdate as "Unknown" or None
        if data.get("bdate") in ("Unknown", None):
            continue

        member = interaction.guild.get_member(int(user_id))
        member_name = member.name if member else "Unknown Member"
        response += f"- {member_name}: {data['bdate']}\n"

    # Send the response
    await interaction.response.send_message(response, ephemeral=False)


#####################################################################################################
# Some utils
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # Return empty structure if file doesn't exist
    except json.JSONDecodeError:
        return {}  # Handle invalid JSON gracefully


# Save data back to the file
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# Update guild data
def get_updated_guild_data(guild_id):
    """Retrieve all birthdays for a specific guild."""
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(guild_id), {})


#####################################################################################################
# Function to increase XP every 15 seconds for members who chatted

# Global dictionary to track when members last sent a message
member_last_activity = {}


async def increase_xp_periodically():
    while True:
        await asyncio.sleep(15)  # Wait for 15 seconds

        data = load_data()
        # print("Current member activity:", member_last_activity)

        # Process guilds in `data`
        for guild_id, guild_data in data.items():
            int_guild_id = int(guild_id)  # Convert to int for comparison
            if int_guild_id not in member_last_activity:
                # print(f"Skipping guild {guild_id} (no activity)")
                continue

            # Process users in the guild
            for user_id, user_data in guild_data.items():
                int_user_id = int(user_id)  # Convert to int for comparison
                if int_user_id not in member_last_activity[int_guild_id]:
                    # print(f"Skipping user {user_id} in guild {guild_id} (no activity)")
                    continue

                last_activity_time = member_last_activity[int_guild_id][int_user_id]
                time_diff = time.time() - last_activity_time

                # print(f"User {user_id} in guild {guild_id}: time_diff={time_diff}")

                # If the member sent a message in the last 15 seconds
                if time_diff > 15:
                    # print(f"Skipping user {user_id} (inactive)")
                    continue

                # Add random XP between 5 and 10
                xp_to_add = random.randint(5, 10)
                user_data["xp"] += xp_to_add
                # print(
                #     f"Added {xp_to_add} XP to user {user_id} in guild {guild_id}. New XP: {user_data['xp']}"
                # )

        save_data(data)  # Save the updated data back to the file

        # Clear the activity tracking dictionary
        member_last_activity.clear()


#####################################################################################################
### XP Commands
from level_card import generate_xp_card, calculate_level_and_thresholds


# Slash command to display the current user's XP and level
@tree.command(
    name="xp", description="Check your current XP and level, or someone else's XP."
)
async def xp(interaction: discord.Interaction, user: discord.User = None):
    """Generate and send an XP card, then delete it after use."""

    # If no user is specified, default to the command issuer
    if user is None:
        user = interaction.user

    user_id = user.id
    guild_id = interaction.guild.id

    # Load the data
    data = load_data()
    guild_id_str = str(guild_id)
    user_id_str = str(user_id)

    # Check if the user exists in the data
    if guild_id_str not in data or user_id_str not in data[guild_id_str]:
        await interaction.response.send_message(
            f"{user.display_name} data was not found. Please interact in the server to be registered.",
            ephemeral=True,
        )
        return

    # Get XP and level data
    user_data = data[guild_id_str][user_id_str]
    xp = user_data.get("xp", 0)

    # Calculate level and thresholds based on XP
    level, current_threshold, next_threshold = calculate_level_and_thresholds(xp)

    # Generate the XP card
    avatar_url = user.display_avatar.url
    username = f"{user.display_name}"  # Display name with discriminator
    card_path = generate_xp_card(
        username,
        avatar_url,
        level,
        xp,
        current_threshold,
        next_threshold,
        "./xp_card_background.png",
    )

    # Send the card as a file
    file = discord.File(card_path, filename="xp_card.png")
    await interaction.response.send_message(file=file)

    # # Optionally, delete the file after sending it
    # if os.path.exists(card_path):
    #     os.remove(card_path)


#####################################################################################################
### Bot events


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


# Function to handle message activity
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


# Event to run when the bot is ready
@client.event
async def on_ready():
    await tree.sync()  # Sync commands to Discord

    # Display activity : Cooking myself kek
    activity = discord.Game(name="Cooking Aki 🤣")
    await client.change_presence(status=discord.Status.online, activity=activity)

    # Indicate login status
    print(f"Logged in as {client.user}")

    # Update birthday data (from data channel)
    update_birthdays.start()

    # Check for people birthday daily
    client.loop.create_task(check_birthdays())

    # Xp
    client.loop.create_task(increase_xp_periodically())


client.run(TOKEN)
