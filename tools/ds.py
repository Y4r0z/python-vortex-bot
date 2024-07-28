import discord
import settings
import lib.vortex_api as Vortex

logger = settings.logging.getLogger('discord')

async def tryGetUser(interaction: discord.Interaction) -> Vortex.User | None:
    """
    Функция пытается найти связанного пользователя Discord через API.
    """
    logger.info(f'Attempt to find user {interaction.user.id} ({interaction.user.name})')
    try:
        link = await Vortex.GetDiscordUser(interaction.user.id)
    except:
        await interaction.response.send_message(content='Вы не привязали ваш аккаунт к Steam, используйте команду `/link`, чтобы сделать это.', ephemeral=True)
        logger.info(f'User not found')
        return None
    logger.info(f'User found: {link['user']["steamId"]}')
    return link['user']


async def checkAdmin(interaction: discord.Interaction):
    """
    Проверка пользователя на права администратора
    """
    logger.info(f'Checking administrator flag for: {interaction.user.id} ({interaction.user.name})')
    if interaction.user.guild_permissions.administrator == False:
        await interaction.response.send_message('Данная команда может быть использована только администратором.', ephemeral=True)
        return False
    return True




def hasRole(member: discord.Member, role_id: int):
    for role in member.roles:
        if role.id == role_id: return True
    return False

async def syncRole(member: discord.Member, role_id: int, privilege_id: int) -> bool:
    """
    Синхронизация роли в Discord с привелегией на сервере
    True - закончить проверки ролей
    False - проверить следующую роль
    """
    logger.info(f'[SyncRole: {member.id}]: Start')
    try:
        user = await Vortex.GetDiscordUser(member.id)
    except:
        # Пользователь не синхронизирован (не найден в БД)
        logger.info(f'[SyncRole: {member.id}]: User not found')
        return True
    steam_id = user['user']['steamId']
    privileges = await Vortex.GetUserPrivileges(steam_id)
    if privilege_id in [i['privilege']['id'] for i in privileges]:
        # Привелегия уже есть у пользователя
        found = next(i for i in privileges if i['privilege']['id'] == privilege_id) # Найденная привелегия
        if found['activeUntil'] == Vortex.BoostyPrivilegeUntil:
            # Эта привелегия из Boosty
            if hasRole(member, role_id):
                # У пользователя есть и роль, и привелегия - проверяем другие роли
                logger.info(f'[SyncRole: {member.id}]: The user already has both role and privilege')
                return False
            # У пользователя есть привелегия, но нет роли - удаляем привелегию
            logger.info(f'[SyncRole: {member.id}]: The user has privilege but not role - removing privilege')
            await Vortex.DeleteUserPrivilege(steam_id, found)
            return False
        # Привелегия не из Boosty
        logger.info(f'[SyncRole: {member.id}]: Found same privilege ({privilege_id}), but not from Boosty - continue')
    # У пользователя нет привелегии
    if not hasRole(member, role_id):
        # У пользователя нет ни роли, ни привелегии - проверяем следуюдую
        logger.info(f'[SyncRole: {member.id}]: Role and privilege not found - abort')
        return False
    # У пользователя нет привелегии, но есть роль - добавляем привелению
    logger.info(f'[SyncRole: {member.id}]: Privilege succsessfully added')
    await Vortex.SetUserPrivilege(steam_id, privilege_id)
    return False
    

async def syncAllRoles(member: discord.Member | discord.User) -> None:
    if not isinstance(member, discord.Member): return
    if \
        await syncRole(member, settings.Preferences['vip_role_id'], Vortex.PrivilegeTypeId.Vip) or \
        await syncRole(member, settings.Preferences['premium_role_id'], Vortex.PrivilegeTypeId.Premium) or \
        await syncRole(member, settings.Preferences['legend_role_id'], Vortex.PrivilegeTypeId.Legend):
        ...