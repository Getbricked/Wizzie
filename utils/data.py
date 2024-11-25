import json
from utils.const import DATA_FILE


#####################################################################################################
# Some utils
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # Return empty structure if file doesn't exist
    except json.JSONDecodeError:
        return {}  # Handle invalid JSON gracefully


# Save data back to the file
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


# Update guild data
def get_updated_guild_data(guild_id):
    """Retrieve all birthdays for a specific guild."""
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(guild_id), {})
