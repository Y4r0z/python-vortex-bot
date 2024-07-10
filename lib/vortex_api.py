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

class PrivilegeTypeId:
    Owner = 1
    Admin = 2
    Moderator = 3
    SoundPad = 4
    MediaPlayer = 5
    Vip = 6
    Premium = 7
    Legend = 8
    CustomPrefix = 9
    WelcomePhrase = 10

class PrivilegeType(TypedDict):
    id: int
    accessLevel: int
    name: str
    description: str
    
class PrivilegeStatus(TypedDict):
    id: int
    privilege: PrivilegeType
    activeUntil: str
    userId: str

BoostyPrivilegeUntil = '2050-01-01T00:00:00'



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

async def SetUserPrivilege(steam_id: str, privilege_id: PrivilegeTypeId):
    async with aiohttp.ClientSession() as session:
        async with session.post(f'{host}/privilege?steam_id={steam_id}&privilege_id={privilege_id}&until={BoostyPrivilegeUntil}', headers=headers) as response:
            ...
        
async def GetUserPrivileges(steam_id: str) -> List[PrivilegeStatus]:
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{host}/privilege/all?steam_id={steam_id}') as r:
            json = await r.json()
            return json

async def DeleteUserPrivilege(steam_id: str, privilege: PrivilegeStatus):
    async with aiohttp.ClientSession() as session:
        async with session.delete(f'{host}/privilege?id={privilege["id"]}', headers=headers):
            return
    