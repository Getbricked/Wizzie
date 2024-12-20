import asyncio
import json
import os
from discord import app_commands
import discord
from datetime import datetime
from utils.birthday import (
    add_or_update_birthday,
    get_updated_guild_birthdays,
    save_birthdays,
)
from utils.const import SETTINGS_FILE
from utils.client import setup_client

# Initialize or load settings data
if not os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({}, f)
with open(SETTINGS_FILE, "r") as f:
    settings = json.load(f)

#####################################################################################################
# Set up the bot client
client, tree = setup_client()


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
