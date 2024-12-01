import json
import discord
import os
from discord import app_commands
from utils.const import SETTINGS_FILE
from utils.client import setup_client

client, tree = setup_client()

# Initialize or load settings data
if not os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({}, f)
with open(SETTINGS_FILE, "r") as f:
    settings = json.load(f)


#####################################################################################################
# Setup commands
@tree.command(
    name="setup",
    description="Bot setup (Admin only)",
)
@app_commands.describe(
    birthday_role="The role to assign for birthdays",
    birthday_channel="The channel for birthday announcements",
    data_channel="The channel for collecting birthday data",
    announcement_channel="The channel for level-up announcements (optional)",
    level_flag="Set to true to enable the level-up system, false to disable (optional)",
)
async def app_setup(
    interaction: discord.Interaction,
    birthday_role: discord.Role,
    birthday_channel: discord.TextChannel,
    data_channel: discord.TextChannel,
    announcement_channel: discord.TextChannel = None,
    level_flag: bool = True,
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need to be an administrator to use this command.", ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    if guild_id not in settings:
        settings[guild_id] = {}

    # Set birthday role, birthday channel, data channel, optional announcement channel, and level flag
    settings[guild_id]["birthday_role"] = birthday_role.name
    settings[guild_id]["birthday_channel"] = birthday_channel.name
    settings[guild_id]["data_channel"] = data_channel.name
    settings[guild_id]["announcement_channel"] = (
        announcement_channel.name if announcement_channel else "Not set"
    )
    settings[guild_id]["level"] = level_flag

    # Save settings to the file
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

    response_message = (
        f"Birthday role set to `{birthday_role.name}`, birthday channel set to `{birthday_channel.name}`, "
        f"and data collection channel set to `{data_channel.name}`!"
    )
    if announcement_channel:
        response_message += (
            f" Level-up announcement channel set to `{announcement_channel.name}`."
        )
    response_message += (
        f" Level-up system has been {'enabled' if level_flag else 'disabled'}."
    )

    await interaction.response.send_message(response_message)
