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

# Static parameters
from utils.const import TOKEN_FILE, DATA_FILE, CURRENT_TIME, SETTINGS_FILE

# Load Token
if not os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "w") as f:
        json.dump({}, f)
with open("token.json", "r") as f:
    TOKEN = json.load(f)["token"]

# Load environment variables
load_dotenv()

#####################################################################################################


# Initialize or load settings data
if not os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({}, f)
with open(SETTINGS_FILE, "r") as f:
    settings = json.load(f)


#####################################################################################################
# Set up the bot client
intents = discord.Intents.default()
intents.members = True  # Needed to access member details
intents.messages = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

from utils.birthday import (
    add_or_update_birthday,
    get_updated_guild_birthdays,
    save_birthdays,
)


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
# Setup commands
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
    with open(SETTINGS_FILE, "w") as f:
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
### XP Commands
from utils.leveling import (
    generate_xp_card,
    calculate_level_and_thresholds,
    calculate_user_rank,
    increase_xp_periodically,
)
from utils.data import load_data, save_data


# Slash command to display the current user's XP and level
@tree.command(name="xp", description="Check XP and level.")
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

    if guild_id_str not in data or user_id_str not in data[guild_id_str]:
        await interaction.response.send_message(
            "Your data was not found. Please interact in the server to be registered.",
            ephemeral=True,
        )
        return

    # Get XP and level data
    user_data = data[guild_id_str][user_id_str]
    xp = user_data.get("xp", 0)

    # Calculate level and thresholds based on XP
    level, current_threshold, next_threshold = calculate_level_and_thresholds(xp)

    # Calculate rank based on XP
    rank = calculate_user_rank(user_id, guild_id)

    # Generate the XP card
    avatar_url = user.display_avatar.url
    username = f"{user.display_name}"
    card_path = generate_xp_card(
        username,
        avatar_url,
        level,
        xp,
        current_threshold,
        next_threshold,
        rank,  # Include the rank in the XP card
        "./xp_card_background.png",
    )

    # Send the card as a file
    file = discord.File(card_path, filename="xp_card.png")
    await interaction.response.send_message(file=file)

    # # Optionally, delete the file after sending it
    # if os.path.exists(card_path):
    #     os.remove(card_path)


@tree.command(
    name="leaderboard", description="Display the XP leaderboard for the server."
)
async def leaderboard(interaction: discord.Interaction):
    """Generate and send the XP leaderboard as an embed."""
    guild_id = interaction.guild.id

    # Load the data
    data = load_data()
    guild_id_str = str(guild_id)

    if guild_id_str not in data:
        await interaction.response.send_message(
            "No data found for this server. Please ensure that XP data has been tracked.",
            ephemeral=True,
        )
        return

    # Get the users' XP data
    guild_data = data[guild_id_str]

    # Prepare the leaderboard data
    leaderboard_data = []
    for user_id_str, user_data in guild_data.items():
        # Skip users with no XP data
        xp = user_data.get("xp", 0)
        if xp == "Unknown":  # If XP is unknown, set it to 0
            xp = 0

        level, current_threshold, next_threshold = calculate_level_and_thresholds(xp)
        rank = calculate_user_rank(
            int(user_id_str), guild_id
        )  # Use the existing function to get the rank
        leaderboard_data.append((user_id_str, rank, xp, level))

    # Sort the leaderboard by rank (ascending order)
    leaderboard_data.sort(key=lambda x: x[1])

    # Create the embed with a black background (using Color(0x000000) for black)
    embed = discord.Embed(
        title="XP Leaderboard",
        description="Top players in the server",
        color=discord.Color(0x000000),  # Black background
    )

    # Add leaderboard entries
    for rank, (user_id_str, user_rank, xp, level) in enumerate(
        leaderboard_data, start=1
    ):
        user = await interaction.guild.fetch_member(
            int(user_id_str)
        )  # Fetch user details
        username = user.display_name if user else "Unknown User"

        # # Apply color to top 3 ranks
        # if user_rank == 1:
        #     color = discord.Color.red()
        # elif user_rank == 2:
        #     color = discord.Color.green()
        # elif user_rank == 3:
        #     color = discord.Color.blue()
        # else:
        #     color = discord.Color(0xFFFFFF)  # Default color for other ranks

        embed.add_field(
            name=f"**#{user_rank}** -  {username}",
            value=f"Level {level} - {xp} XP",
            inline=False,
        )

        # Limit to first 10 users to avoid long messages
        if rank >= 10:
            break

    # Send the embed
    await interaction.response.send_message(embed=embed)


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


# Event to run when the bot is ready

from utils.birthday import check_birthdays, update_birthdays


@client.event
async def on_ready():
    await tree.sync()  # Sync commands to Discord

    # Display activity : Cooking myself kek
    activity = discord.Game(name="Aki 🤣")
    await client.change_presence(status=discord.Status.online, activity=activity)

    # Indicate login status
    print(f"Logged in as {client.user}")

    # Update birthday data (from data channel)
    update_birthdays.start()

    # Check for people birthday daily
    client.loop.create_task(check_birthdays())

    # Xp
    client.loop.create_task(increase_xp_periodically(member_last_activity))


client.run(TOKEN)
