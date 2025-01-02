import discord
from discord import app_commands
import time
from utils.client import setup_client

client, tree = setup_client()


@tree.command(name="clear", description="Delete messages from the current channel.")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(
    interaction: discord.Interaction,
    amount: int = 10,  # The amount of messages to clear
):
    """Delete a specified number of messages from the current channel."""
    channel = interaction.channel

    # Validate the amount to ensure it does not exceed the limit
    if amount > 100:
        await interaction.response.send_message(
            "You can only delete up to 100 messages at a time.", ephemeral=True
        )
        return

    # Defer the response to avoid timeout
    await interaction.response.defer(ephemeral=True)

    if amount <= 0:
        await interaction.followup.send(
            "Please specify a positive number of messages to delete."
        )
        return

    def check(msg):
        time.sleep(0.2)
        return True

    # Purge the messages using the bulk method
    deleted = await channel.purge(limit=amount, check=check)

    # Send a confirmation message
    if deleted:
        await interaction.followup.send(
            f"Deleted {len(deleted)} messages from this channel."
        )
    else:
        await interaction.followup.send("No messages were deleted.")


@clear.error
async def clear_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    """Handle errors for the clear command."""
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "You do not have permission to manage messages, so you cannot use this command.",
            ephemeral=True,
        )
    else:
        # Log the error and send a generic failure message
        print(f"Unexpected error: {error}")
        await interaction.response.send_message(
            "An unexpected error occurred. Please try again later.", ephemeral=True
        )


@tree.command(name="clear-all", description="Delete all messages in the channel.")
@app_commands.checks.has_permissions(administrator=True)
async def clear_all(interaction: discord.Interaction):
    """Deletes all messages in the current channel."""
    channel = interaction.channel
    guild = interaction.guild

    # Defer the response to avoid timeout
    await interaction.response.defer(ephemeral=True)

    # Get the channel's current properties
    channel_name = channel.name
    channel_position = channel.position
    category = channel.category
    overwrites = channel.overwrites  # Permissions for the channel

    # Delete the channel
    await channel.delete()

    # Recreate the channel with the same properties
    await guild.create_text_channel(
        name=channel_name,
        overwrites=overwrites,
        category=category,
        position=channel_position,
    )


@clear_all.error
async def clear_all_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    """Handle errors for the clear-all command."""
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "You do not have the Administrator permission, so you cannot use this command.",
            ephemeral=True,
        )
    else:
        # Log the error and send a generic failure message
        print(f"Unexpected error: {error}")
        await interaction.response.send_message(
            "An unexpected error occurred. Please try again later.", ephemeral=True
        )
