import discord
from discord.ext import tasks
from discord import app_commands
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta

with open("token.json", "r") as f:
    TOKEN = json.load(f)["token"]

# Load environment variables
load_dotenv()


#####################################################################################################
# Initialize or load birthday data
birthdays_file = "birthdays.json"
if not os.path.exists(birthdays_file):
    with open(birthdays_file, "w") as f:
        json.dump({}, f)
with open(birthdays_file, "r") as f:
    birthdays = json.load(f)

# Initialize or load settings data
settings_file = "settings.json"
if not os.path.exists(settings_file):
    with open(settings_file, "w") as f:
        json.dump({}, f)
with open(settings_file, "r") as f:
    settings = json.load(f)


#####################################################################################################
# Set up the bot client
intents = discord.Intents.default()
intents.members = True  # Needed to access member details
intents.messages = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


#####################################################################################################
# Modified task to run at midnight daily
async def check_birthdays():
    while True:
        now = datetime.now()
        # Next update time
        update_time = datetime.combine(
            now.date() + timedelta(days=1), datetime.min.time()
        )

        # Get time from now till next update
        time_until_update = update_time - now

        # Get hours and remaining seconds
        hours, remainder = divmod(time_until_update.seconds, 3600)
        minutes, _ = divmod(remainder, 60)  # Get minutes from the remaining seconds

        # Print the time until the next update
        current_time = datetime.now().strftime("%H:%M")
        print(
            f"{current_time} - Next birthday update in {hours} hours and {minutes} minutes."
        )

        # Wait until midnight
        await asyncio.sleep(time_until_update.seconds)

        # Execute birthday logic at midnight
        today = datetime.now().strftime("%d-%m")
        guild_ids = {data["guild_id"] for data in birthdays.values()}

        for guild_id in guild_ids:
            guild = client.get_guild(int(guild_id))
            if not guild:
                continue  # Skip if the guild is not found

            # Get the birthday role for this guild
            role_name = settings.get(guild_id, {}).get("birthday_role", "Birthday")
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                continue  # Skip if the role doesn't exist

            # Process each member in the guild
            for member in guild.members:
                user_id = str(member.id)
                user_birthday = birthdays.get(user_id, {}).get("date")

                if not user_birthday:
                    continue  # Skip members without birthdays set

                if user_birthday == today:
                    # Assign the birthday role if the user doesn't already have it
                    if role not in member.roles:
                        await member.add_roles(role)
                        channel_name = settings.get(guild_id, {}).get(
                            "birthday_channel", "general"
                        )
                        channel = discord.utils.get(guild.channels, name=channel_name)
                        if channel:
                            await channel.send(
                                f"🎉 Happy Birthday, {member.mention}! 🎂"
                            )
                            print(f"Sent birthday message for: {member.name}")
                elif role in member.roles:
                    # Remove the birthday role if the user's birthday is over
                    await member.remove_roles(role)


#####################################################################################################
# Slash Command to Add a Birthday
@tree.command(
    name="add-birthday", description="Add a birthday for a user (Admins only)"
)
@app_commands.describe(
    user="The user to add a birthday for", date="The user's birthday in DD-MM format"
)
async def add_birthday(
    interaction: discord.Interaction, user: discord.Member, date: str
):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "You need to be an administrator to use this command.", ephemeral=True
        )
        return

    try:
        datetime.strptime(date, "%d-%m")  # Validate date format
    except ValueError:
        await interaction.response.send_message(
            "Invalid date format. Use DD-MM.", ephemeral=True
        )
        return

    # Check if the user's birthday already exists in the data
    user_birthday = birthdays.get(str(user.id))

    if user_birthday:
        # If it exists, update the birthday
        user_birthday["date"] = date
        await interaction.response.send_message(
            f"Updated birthday for {user.display_name} to {date}!"
        )
    else:
        # If it doesn't exist, add the new entry
        birthdays[str(user.id)] = {"date": date, "guild_id": str(interaction.guild.id)}
        await interaction.response.send_message(
            f"Added birthday for {user.name} on {date}!"
        )

    # Save the updated birthdays data to the file
    with open(birthdays_file, "w") as f:
        json.dump(birthdays, f, indent=4)


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

    # Check if the user has birthday data
    user_data = birthdays.get(str(user.id))
    # is_temporary_data = False
    original_has_role = False  # To track if the user already has the birthday role

    if not user_data:
        # Create temporary user data for testing
        user_data = {
            "date": "test",  # Indicate this is temporary test data
            "guild_id": str(guild.id),
        }
        # is_temporary_data = True

    # Get birthday role
    role_name = settings.get(str(guild.id), {}).get("birthday_role", "Birthday")
    role = discord.utils.get(guild.roles, name=role_name)
    if role:
        # Check if the user already has the role
        original_has_role = role in user.roles

        # Assign the role for testing
        if not original_has_role:
            await user.add_roles(role)
        role_message = f"Assigned the role `{role.name}` to {user.display_name}."
    else:
        role_message = "No birthday role is set."

    # Get birthday announcement channel
    channel_name = settings.get(str(guild.id), {}).get("birthday_channel", "general")
    channel = discord.utils.get(guild.channels, name=channel_name)
    if channel:
        await channel.send(f"🎉 (Test) Happy Birthday, {user.mention}! 🎂")
        channel_message = f"Sent a test birthday message in `{channel.name}`."
    else:
        channel_message = "No birthday announcement channel is set."

    await interaction.response.send_message(
        f"Test complete for {user.display_name}.\n{role_message}\n{channel_message}\n"
        "The test role will be removed in 30 seconds.",
        ephemeral=True,
    )

    # Schedule cleanup after 30 seconds
    await asyncio.sleep(30)

    await user.remove_roles(role)
    # print(f"Removed test role from {user.display_name}.")

    # If temporary data was added, no need to persist it
    # if is_temporary_data:
    #     print(f"Temporary test completed for {user.display_name}.")


#####################################################################################################
# Get birthday data from data channel
@tasks.loop(hours=1)  # This task will run every hour
async def update_birthdays():
    # Load the current birthdays from the file (ensure it has the latest data)
    with open("birthdays.json", "r") as f:
        birthdays = json.load(f)

    # Iterate through all guilds
    for guild in client.guilds:
        guild_id = str(guild.id)
        data_channel_name = settings.get(guild_id, {}).get("data_channel")
        if not data_channel_name:
            continue  # Skip if there's no data channel set for this guild

        # Fetch the data channel (where users post their birthdays)
        data_channel = discord.utils.get(guild.text_channels, name=data_channel_name)

        if not data_channel:
            continue  # Skip if the data channel is not found

        # Read the last 100 messages from the channel
        async for message in data_channel.history(limit=100):
            # Skip if the message was sent by a bot
            if message.author.bot:
                continue

            content = message.content.strip()
            if not content:
                continue  # Skip empty messages

            try:
                # Check if the message contains a valid birthday (dd-mm)
                date = datetime.strptime(content, "%d-%m").strftime("%d-%m")

                # If valid, update the birthday data for the user
                user_id = str(message.author.id)
                if (
                    user_id not in birthdays
                ):  # Only add if user doesn't already have a birthday
                    birthdays[user_id] = {"date": date, "guild_id": guild_id}

            except ValueError:
                continue  # Skip invalid date formats

    # After processing all messages, update the birthdays.json file
    with open("birthdays.json", "w") as f:
        json.dump(birthdays, f, indent=4)

    current_time = datetime.now().strftime("%H:%M")
    print(f"{current_time} - Updated birthdays from data channel.")


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

    # Filter birthdays for the current guild
    guild_birthdays = [
        {"member_id": user_id, "date": data["date"]}
        for user_id, data in birthdays.items()
        if data["guild_id"] == guild_id
    ]

    if not guild_birthdays:
        await interaction.response.send_message(
            "No birthdays found for this server.", ephemeral=True
        )
        return

    # Format the list of birthdays
    response = "**🎂 Birthdays in this server:**\n"
    for entry in guild_birthdays:
        member = interaction.guild.get_member(int(entry["member_id"]))
        member_name = member.name if member else "Unknown Member"
        response += f"- {member_name}: {entry['date']}\n"

    # Send the response
    await interaction.response.send_message(response)


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


client.run(TOKEN)
