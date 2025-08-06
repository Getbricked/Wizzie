from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from utils.data import load_data, save_data
import random
import asyncio
import time
import json
import os
from utils.const import SETTINGS_FILE
import discord

# from utils.client import setup_client
# client, tree = setup_client()

#####################################################################################################
# Function to calculate the user's level and thresholds based on their XP


def calculate_level_and_thresholds(xp):
    """Calculate the user's level and the current/next thresholds based on their XP."""
    level = 1
    current_threshold = 0
    next_threshold = 200  # Level 1's threshold ends at 200 XP

    # Keep increasing the level and thresholds while XP surpasses the next threshold
    while xp >= next_threshold:
        level += 1
        current_threshold = next_threshold
        next_threshold = (
            current_threshold + 50 * level
        )  # Increase the threshold each level

    return level, current_threshold, next_threshold


#####################################################################################################
# Function to calculate the user's rank based on their XP in the server


def calculate_user_rank(user_id, guild_id):
    """Calculate the user's rank based on their XP in the server."""
    # Load the data
    data = load_data()
    guild_id_str = str(guild_id)

    if guild_id_str not in data:
        return None  # No data for this server

    # Get all users' XP data in the server
    guild_data = data[guild_id_str]
    users = []

    for user_id_str, user_data in guild_data.items():
        xp = user_data.get("xp", 0)
        users.append((user_id_str, xp))

    # Sort users by XP (highest to lowest)
    users.sort(key=lambda x: x[1], reverse=True)

    # Find the rank of the specific user
    for rank, (user_id_str, xp) in enumerate(users, 1):
        if user_id_str == str(user_id):
            return rank  # Return rank (1-based)

    return None  # In case the user is not found (shouldn't happen)


#####################################################################################################
# Function to check ignore channels
def check_ignore_channel(channel_id, guild_id):
    """Check if the channel is ignored for XP."""
    # Load the settings
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w") as f:
            json.dump({}, f)
    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)

    guild_settings = settings.get(str(guild_id), {})

    ignore_channels = guild_settings.get("ignore_channel", [])

    if channel_id in ignore_channels:
        # print(f"Channel {channel_id} is ignored for XP")
        return True

    return False


#####################################################################################################
# Announce the user's level up in the announcement channel


# Need to pass the `client` object to send messages
async def check_level_up(user_id, guild_id, oldlevel, client):
    """Check if the user leveled up after sending a message."""
    data = load_data()
    guild_id_str = str(guild_id)
    user_id_str = str(user_id)

    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w") as f:
            json.dump({}, f)
    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)

    # print("Checking level up for user", user_id_str, "in guild", guild_id_str)

    if guild_id_str not in data or user_id_str not in data[guild_id_str]:
        return  # No data for this server or user

    user_data = data[guild_id_str][user_id_str]
    xp = user_data.get("xp", 0)
    level, _, _ = calculate_level_and_thresholds(xp)
    # print(xp - current_threshold)
    # Check if the user leveled up
    if level > oldlevel:
        guild = client.get_guild(guild_id)
        user = guild.get_member(user_id)
        # print("User", user_id_str, "leveled up to level", level)
        # Get the announcement channel for the guild
        settings_guild = settings.get(guild_id_str, {})

        # I don't know what this is but somehow it worked lol
        announcement_channel = None

        announcement_channel_name = settings_guild.get("announcement_channel", "")

        if announcement_channel == "":
            return

        if announcement_channel_name == "Not set":
            return

        announcement_channel = discord.utils.get(
            guild.channels, name=announcement_channel_name
        )

        # Announce level-up
        await announcement_channel.send(
            f"🎉 Congratulations {user.mention}! You've leveled up to **Level {level}**! 🎊"
        )


#####################################################################################################
# Function to increase XP every 30 seconds for members who chatted


# Need to pass the `client` object for checking level up
async def increase_xp_periodically(member_last_activity, client):
    while True:
        await asyncio.sleep(30)  # Wait for 30 seconds

        data = load_data()
        # Load settings
        if not os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "w") as f:
                json.dump({}, f)
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)

        # Create a copy of member_last_activity to avoid modifying while iterating
        activity_snapshot = member_last_activity.copy()

        for guild_id, guild_data in data.items():
            int_guild_id = int(guild_id)

            # Skip the guild if the level-up system is disabled
            guild_settings = settings.get(str(guild_id), {})
            if not guild_settings.get("level", True):
                continue

            # Skip if the guild has no activity data
            if int_guild_id not in activity_snapshot:
                continue

            # Process users in the guild with activity
            for user_id, user_data in guild_data.items():
                int_user_id = int(user_id)

                # Skip if the user has no activity data
                for channel_id in activity_snapshot.get(int_guild_id, {}):
                    if int_user_id not in activity_snapshot[int_guild_id].get(channel_id, {}):
                        continue

                    # Check if the channel is ignored for XP
                    if check_ignore_channel(channel_id, guild_id):
                        continue

                    # Get the last activity time for the user
                    last_activity_time = activity_snapshot[int_guild_id][channel_id][int_user_id]

                    # Calculate the time difference since the last activity
                    time_diff = time.time() - last_activity_time

                    # Filter out users inactive more than 30 seconds
                    if time_diff > 30:
                        continue

                    oldlevel, _, _ = calculate_level_and_thresholds(user_data["xp"])
                    # Add random XP between 4 and 8
                    xp_to_add = random.randint(4, 8)
                    user_data["xp"] += xp_to_add

                    save_data(data)

                    # Check if the user leveled up
                    await check_level_up(int_user_id, int_guild_id, oldlevel, client)

        # Clear the activity tracking dictionary after iteration
        member_last_activity.clear()


#####################################################################################################
# Gotta add some packages for this to work (adding arial fonts from windows to linux)


def generate_xp_card(
    username,
    avatar_url,
    level,
    xp,
    current_threshold,
    next_threshold,
    rank,
    background_image_path,
):
    # Dimensions for the card
    width, height = 600, 150
    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))  # Transparent background

    # Load the background image
    background = Image.open(background_image_path).resize((width, height))
    card.paste(background, (0, 0))

    draw = ImageDraw.Draw(card)

    # Load fonts (replace with the path to your fonts)
    font_large = ImageFont.truetype(
        "Arial.ttf", 24
    )
    font_large_bold = ImageFont.truetype(
        "Arial_Bold.ttf", 24
    )  # Bold version
    font_small = ImageFont.truetype(
        "Arial.ttf", 18
    )

    # Define shadow offset
    shadow_offset = (3, 3)  # Offset for the shadow

    # Helper function to draw text with shadow
    def draw_text_with_shadow(
        draw, text, position, font, color, shadow_color, shadow_offset
    ):
        # Draw shadow
        shadow_position = (
            position[0] + shadow_offset[0],
            position[1] + shadow_offset[1],
        )
        draw.text(shadow_position, text, font=font, fill=shadow_color)
        # Draw main text
        draw.text(position, text, font=font, fill=color)

    # Draw user's avatar
    response = requests.get(avatar_url)
    avatar = Image.open(BytesIO(response.content)).resize((100, 100)).convert("RGBA")
    mask = Image.new("L", (100, 100), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, 100, 100), fill=255)
    card.paste(avatar, (20, 25), mask)

    # Draw username with bold font and a darker color with shadow
    draw_text_with_shadow(
        draw,
        username,
        (140, 20),
        font_large_bold,
        (255, 255, 255),  # White color for username
        (0, 0, 0),  # Shadow color (black)
        shadow_offset,
    )

    # Draw rank in orange with shadow, positioned to the right of the username
    draw_text_with_shadow(
        draw,
        f"Rank:",
        (300, 60),  # Positioning rank to the left of the username
        font_large_bold,
        (255, 165, 0),  # Orange color for rank
        (0, 0, 0),  # Shadow color (black)
        shadow_offset,
    )

    # Draw rank number base on rank
    sub = "th"
    rank_color = (255, 255, 255)

    # Check if rank is 1st, 2nd, 3rd, etc.
    if rank % 10 == 1 and rank != 11:
        sub = "st"

    if rank % 10 == 2 and rank != 12:
        sub = "nd"

    if rank % 10 == 3 and rank != 13:
        sub = "rd"

    if rank == 1:
        rank_color = (255, 255, 0)  # Bright yellow color for rank 1

    if rank == 2:
        rank_color = (0, 255, 0)  # Bright green color for rank 2

    if rank == 3:
        rank_color = (100, 206, 255)  # Sky blue color for rank 3

    draw_text_with_shadow(
        draw,
        f"{rank}{sub}",
        (370, 60),  # Positioning rank to the left of the username
        font_large_bold,
        rank_color,  # Color for rank
        (0, 0, 0),  # Shadow color (black)
        shadow_offset,
    )

    # Draw level with bold font and blue color with shadow
    draw_text_with_shadow(
        draw,
        f"Level: {level}",
        (140, 60),
        font_large_bold,
        (0, 200, 255),  # Blue color for level
        (0, 0, 0),  # Shadow color
        shadow_offset,
    )

    # Draw XP with bold font and yellow color with shadow
    draw_text_with_shadow(
        draw,
        f"XP: {xp} / {next_threshold}",
        (140, 90),
        font_large_bold,
        (255, 255, 0),  # Yellow color for XP
        (0, 0, 0),  # Shadow color
        shadow_offset,
    )

    # Draw progress bar
    progress_bar_x = 140
    progress_bar_y = 120
    progress_bar_width = 400
    progress_bar_height = 20

    # Calculate progress
    progress = (xp - current_threshold) / (next_threshold - current_threshold)
    progress_length = int(progress * progress_bar_width)

    # Draw progress bar background
    draw.rectangle(
        [
            progress_bar_x,
            progress_bar_y,
            progress_bar_x + progress_bar_width,
            progress_bar_y + progress_bar_height,
        ],
        fill=(50, 50, 50),  # Dark background for the progress bar
    )
    # Draw progress bar fill
    draw.rectangle(
        [
            progress_bar_x,
            progress_bar_y,
            progress_bar_x + progress_length,
            progress_bar_y + progress_bar_height,
        ],
        fill=(0, 200, 255),  # Blue color for the progress bar
    )

    # Save or return the card
    output_path = "./xp_card.png"
    card.save(output_path)
    return output_path


# Example usage with a background image path
# generate_xp_card(
#     "Maria behave when??",
#     "https://cdn.discordapp.com/attachments/1108373856613306458/1227580443352633407/image.png?ex=67445ee1&is=67430d61&hm=058f6e6ea395e38ef28130e4f3867117c44ecf70fa796d8876a9a8f89c627d33&",
#     5,
#     800,
#     500,
#     1000,
#     1,
#     "xp_card_background.png",  # Path to your background image
# )
