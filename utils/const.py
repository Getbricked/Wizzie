from datetime import datetime
import json
import os

TOKEN_FILE = "token.json"
DATA_FILE = "data.json"
CURRENT_TIME = datetime.now().strftime("%H:%M")
SETTINGS_FILE = "settings.json"
DB_CONFIG_FILE = "db_config.json"


# Load Token
def load_token():
    """Load token from token.json file."""
    if not os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "w") as f:
            json.dump({}, f)
    try:
        with open(TOKEN_FILE, "r") as f:
            return json.load(f).get("token")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading token: {e}")
        return None


# Load Database Configuration
def load_db_config():
    """Load database configuration from db_config.json file."""
    try:
        if not os.path.exists(DB_CONFIG_FILE):
            print(f"Database config file not found at {DB_CONFIG_FILE}")
            return None
        with open(DB_CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Database config file not found at {DB_CONFIG_FILE}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing database config JSON: {e}")
        return None


TOKEN = load_token()
DB_CONFIG = load_db_config()
