from dotenv import load_dotenv
import os
import pathlib
import json
from typing import TypedDict

class PreferencesStructure(TypedDict):
    vip_role_id: int
    premium_role_id: int
    legend_role_id: int


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
STEAM_TOKEN = os.getenv("STEAM_TOKEN")
VORTEX_TOKEN = os.getenv("VORTEX_TOKEN")
VORTEX_HOST = os.getenv("VORTEX_HOST")
GUILD_ID = os.getenv("GUILD_ID")
Preferences : PreferencesStructure | None = None


preferences_dir = 'preferences'
preferences_file = 'ids.json'
path = f'{preferences_dir}/{preferences_file}'
pathlib.Path(preferences_dir).mkdir(parents=True, exist_ok=True)
if pathlib.Path(path).is_file():
    with open(path, 'r') as f:
        PREFERENCES = json.load(f)

def SavePreferences():
    if Preferences is None: return
    with open(path, 'w') as f:
        json.dump(Preferences, f)