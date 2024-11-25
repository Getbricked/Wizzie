from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
from utils.data import load_data, save_data
import random
import asyncio
import time

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
        level, current_threshold, next_threshold = calculate_level_and_thresholds(xp)
        users.append((user_id_str, xp, level))

    # Sort users by XP (highest to lowest)
    users.sort(key=lambda x: x[1], reverse=True)

    # Find the rank of the specific user
    for rank, (user_id_str, xp, level) in enumerate(users, 1):
        if user_id_str == str(user_id):
            return rank  # Return rank (1-based)

    return None  # In case the user is not found (shouldn't happen)


#####################################################################################################
# Function to increase XP every 15 seconds for members who chatted


async def increase_xp_periodically(member_last_activity):
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
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf", 24
    )
    font_large_bold = ImageFont.truetype(
        "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf", 24
    )  # Bold version
    font_small = ImageFont.truetype(
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf", 18
    )

    # Define shadow offset
    shadow_offset = (2, 2)  # Offset for the shadow

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

    # Draw rank (#1) in red with shadow, positioned to the right of the username
    draw_text_with_shadow(
        draw,
        f"Rank: #{rank}",
        (300, 60),  # Positioning rank to the left of the username
        font_large_bold,
        (255, 0, 0),  # Red color for rank
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
#     "xp_card_background.png",  # Path to your background image
# )
