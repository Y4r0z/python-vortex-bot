from dotenv import load_dotenv
import os
import pathlib
import json
from typing import TypedDict
from logging.config import dictConfig
import logging

class PreferencesStructure(TypedDict):
    vip_role_id: int
    premium_role_id: int
    legend_role_id: int


load_dotenv()
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN")
STEAM_TOKEN: str = os.getenv("STEAM_TOKEN")
VORTEX_TOKEN: str = os.getenv("VORTEX_TOKEN")
VORTEX_HOST: str = os.getenv("VORTEX_HOST")
GUILD_ID: str = os.getenv("GUILD_ID")
Preferences : PreferencesStructure = {}

assert DISCORD_TOKEN, 'Не указан токен Discord - DISCORD_TOKEN'
assert STEAM_TOKEN, 'Не указан ключ Steam API - STEAM_TOKEN'
assert VORTEX_TOKEN, 'Не указан токен Vortex API - VORTEX_TOKEN'
assert VORTEX_HOST, 'Не указан адрес сервера Vortex API - VORTEX_HOST'
assert GUILD_ID, 'Не указан токен сервера - GUILD_ID'


BASE_DIR = pathlib.Path(__file__).parent
COGS_DIR = BASE_DIR / "cogs"


preferences_dir = 'preferences'
preferences_file = 'ids.json'
path = os.path.join(preferences_dir, preferences_file)
pathlib.Path(preferences_dir).mkdir(parents=True, exist_ok=True)
pathlib.Path('./logs').mkdir(parents=True, exist_ok=True)
if pathlib.Path(path).is_file():
    with open(path, 'r') as f:
        Preferences = json.load(f)

def SavePreferences():
    if len(Preferences.items()) ==  0: return
    with open(path, 'w') as f:
        json.dump(Preferences, f)

def IsSetUp():
    return all(i in Preferences.keys() for i in ['vip_role_id', 'premium_role_id', 'legend_role_id'])


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(levelname)-10s - %(asctime)s - %(module)-15s : %(message)s"
        },
        "standart": {
            "format": "%(levelname)-10s - %(asctime)s - %(name)-15s : %(message)s"
        }
    },
    "handlers":{
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "standart"
        },
         "console2": {
            "level": "WARNING",
            "class": "logging.StreamHandler",
            "formatter": "standart"
        },
         "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "logs/info.log",
            "formatter": "verbose",
            "mode": "w"
        }
    },
    "loggers": {
        "bot":{
            "handlers": ['console'],
            "level": "INFO",
            "propogate": False
        },
        "discord": {
            "handlers": ['console2', 'file'],
            "level": "INFO",
            "propogaate": False
        }
    }
}

dictConfig(LOGGING_CONFIG)