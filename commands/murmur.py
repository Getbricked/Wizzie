import discord
from discord import app_commands
from utils.client import setup_client

client, tree = setup_client()

# Define the static image URL
STATIC_IMAGE_URL = "https://cdn.discordapp.com/emojis/1335981860655988798.webp"  # Replace with your actual image URL


@tree.command(
    name="murmur",
    description="Send a whisper with a censored message and an image in the current channel.",
)
@app_commands.describe(
    user="The user to tag in the whisper.",
    msg="The message to send (will be censored).",
)
async def murmur(
    interaction: discord.Interaction,
    user: discord.User,
    msg: str,
):
    """Send a whisper in the current channel with a censored message and a predefined image."""
    try:
        # Mention the user being whispered to first
        await interaction.channel.send(f"{user.mention}")

        # Create an embed with the censored message
        censored_msg = f"**{interaction.user.mention} whispered to {user.mention}:**\n||**{msg}**||"
        embed = discord.Embed(description=censored_msg, color=discord.Color.blue())
        embed.set_image(url=STATIC_IMAGE_URL)  # Use the predefined image URL

        # Send the embed
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message(
            f"Whisper sent in this channel!", ephemeral=True
        )
    except Exception as e:
        # Handle any unexpected errors
        print(f"Unexpected error: {e}")
        await interaction.response.send_message(
            "An unexpected error occurred. Please try again later.", ephemeral=True
        )


@murmur.error
async def whisper_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    """Handle errors for the whisper command."""
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )
    else:
        # Log the error and send a generic failure message
        print(f"Unexpected error: {error}")
        await interaction.response.send_message(
            "An unexpected error occurred. Please try again later.", ephemeral=True
        )
