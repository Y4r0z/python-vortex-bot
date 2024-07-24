import discord
import settings
from discord.ext import commands
from tools.discord import checkAdmin
import lib.vortex_api as Vortex

logger = settings.logging.getLogger('discord')


def hasRole(member: discord.Member, role_id: int):
    for role in member.roles:
        if role.id == role_id: return True
    return False

def compareRoles(before: discord.Member, after: discord.Member, role_id: int):
    if hasRole(after, role_id) and not hasRole(before, role_id):
        return 1
    elif not hasRole(after, role_id) and hasRole(before, role_id):
        return -1
    return 0

async def manageRole(before: discord.Member, after: discord.Member, role_id: int, privilege_id: int) -> bool:
    """
    True - закончить проверки ролей
    False - проверить следующую роль
    """
    logger.info(f'Managing role: {role_id} (privilege: {privilege_id})')
    diff = compareRoles(before, after, role_id)
    if diff == 0:
        logger.info('Roles count are equal: check next')
        return False
    try:
        user = await Vortex.GetDiscordUser(before.id)
    except:
        logger.info("User not found: cancel")
        return True
    steam_id = user['user']['steamId']
    privs = await Vortex.GetUserPrivileges(steam_id)
    if diff == 1:
        logger.info('More roles found after update')
        if privilege_id in [i['privilege']['id'] for i in privs]:
             logger.info('Mentioned privilege found in user privileges')
             p = next(i for i in privs if i['privilege']['id'] == privilege_id)
             logger.info(f'Privilege: {p["privilege"]["name"]}')
             if p['activeUntil'] == Vortex.BoostyPrivilegeUntil:
                 logger.info('Found privilege was given by this bot: check next')
                 return False
        logger.info('No equal roles in user privileges, setting a role: cancel')
        await Vortex.SetUserPrivilege(steam_id, privilege_id)
        return True
    logger.info('Less roles found after update')
    if privilege_id not in [i['privilege']['id'] for i in privs]:
        logger.info('Mentioned privilege not found in user privileges: check next')
        return False
    logger.info('Privilege found, removing privilege: cancel')
    p = next(i for i in privs if i['privilege']['id'] == privilege_id)
    await Vortex.DeleteUserPrivilege(steam_id, p)
    return True




class MemberUpdateEvent(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        logger.info(f'Member update event for {before.id} ({before.name}))')
        if not settings.IsSetUp():
            logger.error('Bot is not set up: return')
            return
        if len(before.roles) == len(after.roles):
            logger.info('No changes in roles detected: return')
            return
        if \
            await manageRole(before, after, settings.Preferences['vip_role_id'], Vortex.PrivilegeTypeId.Vip) or \
            await manageRole(before, after, settings.Preferences['premium_role_id'], Vortex.PrivilegeTypeId.Premium) or \
            await manageRole(before, after, settings.Preferences['legend_role_id'], Vortex.PrivilegeTypeId.Legend):
            logger.info('Some of roles changed')
        # Если одна роль изменна, то остальные не трогать. Использую особенность "ленивых" выражений в python
        logger.info('Member update: Ok')


async def setup(bot: commands.Bot):
    await bot.add_cog(MemberUpdateEvent(bot), guild=discord.Object(id = settings.GUILD_ID))