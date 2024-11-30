import discord
from discord import app_commands

# Set up the bot client


def setup_client():
    intents = discord.Intents.default()
    intents.members = True  # Needed to access member details
    intents.messages = True
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    return client, tree
