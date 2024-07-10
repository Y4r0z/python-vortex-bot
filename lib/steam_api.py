import aiohttp
import settings
from typing import TypedDict


key = settings.STEAM_TOKEN

class PlayerSummary(TypedDict):
    steamid: str
    communityvisibilitystate: int
    profilestate: int
    personaname: str
    commentpermission: int
    profileurl: str
    avatar: str
    avatarmedium: str
    avatarfull: str
    avatarhash: str
    lastlogoff: int
    personastate: int
    realname: str
    primaryclanid: str
    timecreated: int
    personastateflags: int
    loccountrycode: str
    locstatecode: str



async def GetPlayerSummaries(steam_id: str) -> PlayerSummary:
    async with aiohttp.ClientSession() as session:
            async with session.get(f'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={key}&steamids={steam_id}') as response:
                json = await response.json()
                if not json or not json['response'] or not json['response']['players'] or len(json['response']['players']) == 0:
                     raise Exception("Игрок не найден")
                return json['response']['players'][0]