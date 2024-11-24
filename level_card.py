from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO


# Calculate level
def calculate_level(xp):
    """Calculate the user's level based on their XP."""
    level = 1
    xp_threshold = 300  # Initial threshold for level 1

    # Keep incrementing the level while XP exceeds the threshold
    while xp > xp_threshold:
        level += 1
        xp_threshold += 200  # Threshold increases by 200 each level

    return level


def generate_xp_card(
    username, avatar_url, level, xp, current_threshold, next_threshold
):
    # Dimensions for the card
    width, height = 600, 150
    card = Image.new("RGBA", (width, height), (30, 30, 30, 255))  # Background color

    draw = ImageDraw.Draw(card)

    # Load fonts (replace with the path to your fonts)
    font_large = ImageFont.truetype("arial.ttf", 24)
    font_small = ImageFont.truetype("arial.ttf", 18)

    # Draw user's avatar
    response = requests.get(avatar_url)
    avatar = Image.open(BytesIO(response.content)).resize((100, 100)).convert("RGBA")
    mask = Image.new("L", (100, 100), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, 100, 100), fill=255)
    card.paste(avatar, (20, 25), mask)

    # Draw username and details
    draw.text((140, 20), username, font=font_large, fill=(255, 255, 255))
    draw.text((140, 60), f"Level: {level}", font=font_small, fill=(200, 200, 200))
    draw.text(
        (140, 90),
        f"XP: {xp} / {next_threshold}",
        font=font_small,
        fill=(200, 200, 200),
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
        fill=(50, 50, 50),
    )
    # Draw progress bar fill
    draw.rectangle(
        [
            progress_bar_x,
            progress_bar_y,
            progress_bar_x + progress_length,
            progress_bar_y + progress_bar_height,
        ],
        fill=(0, 200, 255),
    )

    # Save or return the card
    output_path = "./xp_card.png"
    card.save(output_path)
    return output_path
