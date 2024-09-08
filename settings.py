from dotenv import load_dotenv
import os
import pathlib
import json
from typing import TypedDict, Literal, Any, TypeVar, Callable, Optional
from logging.config import dictConfig
import logging

class PreferencesStructure(TypedDict):
    vip_role_id: int
    premium_role_id: int
    legend_role_id: int
    linked_role_id: int
    moder_role_id: int
    bot_output_channel_id: int

class RoleNames:
    Vip = 'vop_role_id'
    Premium = 'premium_role_id'
    Legend = 'legend_role_id'
    Moder = 'moder_role_id'
    Linked = 'linked_role_id'

class ChannelNames:
    BotOutput = 'bot_output_channel_id'
    
RolesLiteral = Literal['vip_role_id', 'premium_role_id', 'legend_role_id', 'moder_role_id', 'linked_role_id']
ChannelsLiteral = Literal['bot_output_channel_id']
PreferencesLiteral = Literal['vip_role_id', 'premium_role_id', 'legend_role_id', 'moder_role_id', 'linked_role_id', 'bot_output_channel_id']

load_dotenv()
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN") # type: ignore
STEAM_TOKEN: str = os.getenv("STEAM_TOKEN") # type: ignore
VORTEX_TOKEN: str = os.getenv("VORTEX_TOKEN") # type: ignore
VORTEX_HOST: str = os.getenv("VORTEX_HOST") # type: ignore
GUILD_ID: str = os.getenv("GUILD_ID") # type: ignore
Preferences : PreferencesStructure = {} # type: ignore

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
    return all(i in Preferences.keys() for i in [
        'vip_role_id', 'premium_role_id', 'legend_role_id', 'linked_role_id'])

def IsCommandsSetUp():
    return all(i in Preferences.keys() for i in ['moder_role_id'])

def IsChannelsSetUp():
    return all(i in Preferences.keys() for i in ['bot_output_channel_id'])

def IsRoleExists(role_name: RolesLiteral) -> bool:
    return role_name in Preferences.keys() and Preferences[role_name] is not None

def IsChannelExists(channel_name: ChannelsLiteral) -> bool:
    return channel_name in Preferences.keys() and Preferences[channel_name] is not None


__defaultProcessor = lambda x: int(x)
T = TypeVar('T', bound=Any)
def Get(
    setting_name: PreferencesLiteral, 
    defaultValue: T = None, # type: ignore
    processor: Callable[[int], T] = __defaultProcessor, # type: ignore
):
    if setting_name in Preferences.keys() and Preferences[setting_name] is not None:
        return processor(Preferences[setting_name])
    return defaultValue

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