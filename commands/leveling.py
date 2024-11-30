import discord
import os
from discord import app_commands


from utils.client import setup_client

client, tree = setup_client()

#####################################################################################################
### XP Commands
from utils.leveling import (
    generate_xp_card,
    calculate_level_and_thresholds,
    calculate_user_rank,
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
