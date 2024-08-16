import aiohttp
import settings
import datetime
from typing import TypedDict, List, Union
from lib.steam_api import PlayerSummary



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

class PrivilegeSet(TypedDict):
    owner: bool
    admin: bool
    moderator: bool
    soundpad: bool
    mediaPlayer: bool
    vip: bool
    premium: bool
    legend: bool
    customPrefix: str
    welcomePhrase: str

class MoneyDrop(TypedDict):
    user: User
    value: int
    nextDrop: str

class Giveaway(TypedDict):
    id: int
    user: User
    timeCreated: str
    activeUntil: str
    maxUseCount: int
    curUseCount: int
    reward: int
    status: int

class StatusCode(TypedDict):
    status: int

class ChatLog(TypedDict):
    id: int
    steamId: str
    nickname: str
    text: str
    time: str
    server: str
    team: int
    chatTeam: int

class TopEntry(TypedDict):
    rank: int
    steamId: str
    score: int
    steamInfo: PlayerSummary

class PerkSet(TypedDict):
    survivorPerk1: str
    survivorPerk2: str
    survivorPerk3: str
    survivorPerk4: str
    boomerPerk: str
    smokerPerk: str
    hunterPerk: str
    jockeyPerk: str
    spitterPerk: str
    chargerPerk: str
    tankPerk: str

class BulkProfileInfo(TypedDict):
    steamInfo: PlayerSummary
    rank: int | None
    balance: int
    perks: PerkSet | None
    privileges: list[PrivilegeStatus]
    discordId: int | None

class Rank(TypedDict):
    rank: int
    score: int
    


def PrivilegeSetToString(ps: PrivilegeSet):
    lst = []
    if ps['owner']: lst.append('Владелец (owner)')
    if ps['admin']: lst.append('Администратор (admin)')
    if ps['moderator']: lst.append('Модератор (moderator)')
    if ps['soundpad']: lst.append('Доступ к саундпаду (soundpad)')
    if ps['mediaPlayer']: lst.append('Доступ к проигрывателю (mediaPlayer)')
    if ps['vip']: lst.append('VIP')
    if ps['premium']: lst.append('Premium')
    if ps['legend']: lst.append('Legend')
    if len(ps['customPrefix']) > 0: lst.append(f'Префикс в чате: [{ps['customPrefix']}]')
    if len(ps['welcomePhrase']) > 0: lst.append(f'Привественная фраза: "{ps['welcomePhrase']}"')
    return '\n'.join(lst)

BoostyPrivilegeUntil = '2050-01-01T00:00:00'

async def _Get(href: str, supressErrors = False):
    async with aiohttp.ClientSession() as session:
        async with session.get(href) as response:
            if response.status // 100 != 2 and not supressErrors: raise Exception(f'HTTP ERROR: {response.start}')
            return await response.json()
        
async def _Post(href: str, data = None, supressErrors = False):
    async with aiohttp.ClientSession() as session:
        async with session.post(href, headers=headers, json=data) as response:
            if response.status // 100 != 2 and not supressErrors: raise Exception(f'HTTP ERROR: {response.start}')
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
    return await _Get(f'{host}/discord?discord_id={discord_id}')

async def GetDiscordUserSteam(steam_id: str) -> SteamLink:
    return await _Get(f'{host}/discord/steam?steam_id={steam_id}')

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

async def GetPrivilegeSet(steam_id: str) -> PrivilegeSet:
    return await _Get(f'{host}/privilege?steam_id={steam_id}')

async def GetMoneyDrop(steam_id: str) -> MoneyDrop:
    return await _Get(f'{host}/balance/drop?steam_id={steam_id}')

async def CreateGiveaway(steam_id: str, useCount: int, reward: int, minutes: int) -> Giveaway:
    """
    @param useCount: сколько раз можно забрать награду
    @param reward : количество коинов в качестве награды
    @param minutes: сколько минут длится раздача
    """
    payload = {
        'useCount': useCount,
        'reward': reward,
        'activeUntil': (datetime.datetime.now(datetime.UTC).replace(microsecond=0) + datetime.timedelta(minutes=minutes)).isoformat()
    }
    return await _Post(f'{host}/balance/giveaway?steam_id={steam_id}', data=payload, supressErrors=True)

async def CheckoutGiveaway(steam_id: str, giveaway_id: int) -> Giveaway:
    return await _Get(f'{host}/balance/giveaway/checkout?steam_id={steam_id}&giveaway_id={giveaway_id}', supressErrors=True)

async def DeleteGiveaway(giveaway_id: int):
    return await _Delete(f'{host}/balance/giveaway?giveaway_id={giveaway_id}')

async def GetGiveaways(steam_id: str) -> List[Giveaway]:
    return await _Get(f'{host}/balance/giveaway/all?steam_id={steam_id}')

async def GetLogs(
    text: str | None,
    steam_id: str | None,
    nickname: str | None,
    server: str | None,
    offset: int = 0,
    limit: int = 15
) -> List[ChatLog]:
    href = f'{host}/logs?limit={limit}&offset={offset}'
    if text: href += f'&text={text}'
    if steam_id: href += f'&steam_id={steam_id}'
    if nickname: href += f'&nickname={nickname}'
    if server: href += f'&server={server}'
    return await _Get(href)
    
    
async def GetScoreTop(offset: int = 0, limit: int = 10) -> List[TopEntry]:
    return await _Get(f'{host}/score/top?limit={limit}&offset={offset}')

async def GetPlayerRank(steam_id: str) -> Rank:
    return await _Get(f'{host}/score/top/rank?steam_id={steam_id}')

async def GetBulkProfile(steam_id: str) -> BulkProfileInfo:
    return await _Get(f'{host}/profile/bulk?steam_id={steam_id}&cached=False')