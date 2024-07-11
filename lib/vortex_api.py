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

class Balance(TypedDict):
    id: int
    user: User
    value: int

class DuplexTransaction(TypedDict):
    id: int
    source: Balance
    target: Balance
    value: int
    description: str

BoostyPrivilegeUntil = '2050-01-01T00:00:00'

async def _Get(href: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(href) as response:
            if response.status // 100 != 2: raise Exception(f'HTTP ERROR: {response.start}')
            return await response.json()
        
async def _Post(href: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(href, headers=headers) as response:
            if response.status // 100 != 2: raise Exception(f'HTTP ERROR: {response.start}')
            return await response.json()

async def _Delete(href: str):
    async with aiohttp.ClientSession() as session:
        async with session.delete(href, headers=headers) as response:
            if response.status // 100 != 2: raise Exception(f'HTTP ERROR: {response.start}')
            return await response.json()




async def FindSteamUser(steam_id: str) -> List[User]:
    return await _Get(f'{host}/user/search?query={steam_id}')

async def LinkUser(steam_id: str, discord_id: str | int) -> SteamLink:
    return await _Post(f'{host}/discord?steam_id={steam_id}&discord_id={discord_id}')

async def GetDiscordUser(discord_id: str | int) -> SteamLink:
    return await _Get(f'{host}/discord?&discord_id={discord_id}')

async def SetUserPrivilege(steam_id: str, privilege_id: int):
    return await _Post(f'{host}/privilege?steam_id={steam_id}&privilege_id={privilege_id}&until={BoostyPrivilegeUntil}')
        
async def GetUserPrivileges(steam_id: str) -> List[PrivilegeStatus]:
    return await _Get(f'{host}/privilege/all?steam_id={steam_id}')

async def DeleteUserPrivilege(steam_id: str, privilege: PrivilegeStatus):
    return await _Delete(f'{host}/privilege?id={privilege["id"]}')

async def GetBalance(steam_id: str) -> Balance:
    return await _Get(f'{host}/balance?steam_id={steam_id}') 

async def AddBalance(steam_id: str, value: int):
    return await _Post(f'{host}/balance/add?steam_id={steam_id}&value={value}')

async def PayBalance(source_id: str, target_id: str, value: int) -> DuplexTransaction:
    return await _Post(f'{host}/balance/pay?source_steam_id={source_id}&target_steam_id={target_id}&value={value}')

