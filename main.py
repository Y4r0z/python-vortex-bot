import settings
import discord
from discord.ext import commands
from ui.steam_link import LinkView
import lib.vortex_api as Vortex
from ui.setup import SetupView

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
    diff = compareRoles(before, after, role_id)
    if diff == 0: return False
    try:
        user = await Vortex.GetDiscordUser(before.id)
    except: return True
    steam_id = user['user']['steamId']
    privs = await Vortex.GetUserPrivileges(steam_id)
    if diff == 1:
        if privilege_id in [i['privilege']['id'] for i in privs]:
             p = next(i for i in privs if i['privilege']['id'] == privilege_id)
             if p['activeUntil'] == Vortex.BoostyPrivilegeUntil: return False
        await Vortex.SetUserPrivilege(steam_id, privilege_id)
        return True
    if privilege_id not in [i['privilege']['id'] for i in privs]: return False
    p = next(i for i in privs if i['privilege']['id'] == privilege_id)
    await Vortex.DeleteUserPrivilege(steam_id, p)
    return True
    

def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    guild = discord.Object(id=settings.GUILD_ID)

    bot = commands.Bot(intents=intents, command_prefix='!')    

    @bot.event
    async def on_ready():
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)

    @bot.event
    async def on_member_update(before: discord.Member, after: discord.Member):
        if not settings.IsSetUp(): return
        if len(before.roles) == len(after.roles): return
        if \
            await manageRole(before, after, settings.Preferences['vip_role_id'], Vortex.PrivilegeTypeId.Vip) or \
            await manageRole(before, after, settings.Preferences['premium_role_id'], Vortex.PrivilegeTypeId.Premium) or \
            await manageRole(before, after, settings.Preferences['legend_role_id'], Vortex.PrivilegeTypeId.Legend):
            ...
        # Если одна роль изменна, то остальные не трогать
        

    @bot.tree.command(name='setup', description='Настраивает бота в данном канале')
    async def setupcommand(interaction: discord.Interaction):
        view = SetupView()
        await interaction.response.send_message(content='Настройка бота', view=view, ephemeral=True)

    bot.run(settings.DISCORD_TOKEN)


if __name__ == '__main__':
    main()