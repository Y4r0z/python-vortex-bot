import aiohttp
import settings
from typing import TypedDict, List


host = settings.VORTEX_HOST
token = settings.VORTEX_TOKEN
headers = {'Authorization': f'Bearer {token}'}

class User(TypedDict):
    id: int
    steamId: str

class SteamLink(TypedDict):
    id: int
    discordId: str
    user: User


async def FindSteamUser(steam_id: str) -> List[User]:
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{host}/user/search?query={steam_id}') as response:
            json = await response.json()
            return json

async def LinkUser(steam_id: str, discord_id: str | int) -> SteamLink:
    async with aiohttp.ClientSession() as session:
        async with session.post(f'{host}/discord?steam_id={steam_id}&discord_id={discord_id}', headers=headers) as response:
            json = await response.json()
            return json

async def GetDiscordUser(discord_id: str | int) -> SteamLink:
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{host}/discord?&discord_id={discord_id}') as response:
            json = await response.json()
            return json