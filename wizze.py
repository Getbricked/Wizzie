import discord
from discord.ext import tasks
from discord import app_commands
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta


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
# Event to run when the bot is ready
@client.event
async def on_ready():
    await tree.sync()  # Sync commands to Discord
    activity = discord.Game(name="Cooking Aki 🤣")
    await client.change_presence(status=discord.Status.online, activity=activity)
    print(f"Logged in as {client.user}")
    update_birthdays.start()
    client.loop.create_task(check_birthdays())  # Start the birthday checker


#####################################################################################################
# Event to run on member join
# Load the JSON data file
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


# Event when a member joins a guild
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


client.run(TOKEN)
