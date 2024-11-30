from datetime import datetime
import json
import os

TOKEN_FILE = "token.json"
DATA_FILE = "data.json"
CURRENT_TIME = datetime.now().strftime("%H:%M")
SETTINGS_FILE = "settings.json"

# Load Token
if not os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "w") as f:
        json.dump({}, f)
with open("token.json", "r") as f:
    TOKEN = json.load(f)["token"]
