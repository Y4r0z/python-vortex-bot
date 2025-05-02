import discord
import settings
import lib.vortex_api as Vortex
import lib.steam_api as Steam
import asyncio
import datetime
from typing import Optional, Tuple, Literal

logger = settings.logging.getLogger('discord.info')
sync_logger = settings.logging.getLogger('sync')

async def tryGetUser(interaction: discord.Interaction) -> Optional[Vortex.User]:
    """
    Функция пытается найти связанного пользователя Discord через API.
    
    Args:
        interaction: Объект взаимодействия Discord
        
    Returns:
        Optional[Vortex.User]: Данные пользователя или None если не найден
    """
    logger.info(f'Attempt to find user {interaction.user.id} ({interaction.user.name})')
    try:
        link = await _retry_api_call(
            lambda: Vortex.GetDiscordUser(interaction.user.id)
        )
        if not link:
            await interaction.response.send_message(
                content='Вы не привязали ваш аккаунт к Steam, используйте команду `/link`, чтобы сделать это.',
                ephemeral=True
            )
            logger.info(f'User not found')
            return None
            
        logger.info(f'User found: {link["user"]["steamId"]}')
        return link['user']
    except Exception as e:
        logger.error(f'Error getting user: {str(e)}')
        await interaction.response.send_message(
            content='Произошла ошибка при поиске аккаунта. Попробуйте позже.',
            ephemeral=True
        )
        return None

async def checkAdmin(interaction: discord.Interaction) -> bool:
    """
    Проверка пользователя на права администратора
    
    Args:
        interaction: Объект взаимодействия Discord
        
    Returns:
        bool: True если пользователь администратор, иначе False
    """
    if not isinstance(interaction.user, discord.Member):
        return False
        
    logger.info(f'Checking administrator flag for: {interaction.user.id} ({interaction.user.name})')
    
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            'Данная команда может быть использована только администратором.',
            ephemeral=True
        )
        return False
    return True

def hasRole(member: discord.Member, role_id: int) -> bool:
    """
    Проверяет наличие роли у пользователя
    
    Args:
        member: Объект участника Discord
        role_id: ID роли
        
    Returns:
        bool: True если роль найдена, иначе False
    """
    return any(role.id == role_id for role in member.roles)

async def _retry_api_call(func, max_attempts: int = settings.API_RETRY_ATTEMPTS):
    """
    Выполняет API вызов с повторными попытками при неудаче
    
    Args:
        func: Асинхронная функция для выполнения
        max_attempts: Максимальное количество попыток
        
    Returns:
        Результат выполнения функции
        
    Raises:
        Exception: Если все попытки неудачны
    """
    for attempt in range(max_attempts):
        try:
            return await asyncio.wait_for(
                func(),
                timeout=settings.API_TIMEOUT
            )
        except asyncio.TimeoutError:
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(settings.API_RETRY_DELAY)
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            logger.warning(f'API call failed (attempt {attempt + 1}): {str(e)}')
            await asyncio.sleep(settings.API_RETRY_DELAY)

async def check_privilege_status(
    privileges: list,
    privilege_id: int
) -> Tuple[Literal['active', 'expired', 'missing'], Optional[dict]]:
    """
    Проверяет статус привилегии пользователя
    
    Args:
        privileges: Список привилегий пользователя
        privilege_id: ID привилегии для проверки
        
    Returns:
        Tuple[str, Optional[dict]]: (Статус привилегии, Данные привилегии если найдена)
    """
    for privilege in privileges:
        if privilege['privilege']['id'] != privilege_id:
            continue
            
        sync_logger.debug(f"Checking privilege: {privilege['privilege']['name']}, active until: {privilege['activeUntil']}")
        
        if privilege['activeUntil'] == Vortex.BoostyPrivilegeUntil:
            return 'active', privilege
            
        try:
            active_until_str = privilege['activeUntil']
            
            if 'Z' in active_until_str:
                active_until_str = active_until_str.replace('Z', '+00:00')
            elif '+' not in active_until_str and '-' not in active_until_str[10:]:
                active_until_str = active_until_str + '+00:00'
                
            active_until = datetime.datetime.fromisoformat(active_until_str)
            now = datetime.datetime.now(datetime.timezone.utc)
            
            sync_logger.debug(f"Active until: {active_until}, now: {now}")
            
            if active_until > now:
                return 'active', privilege
            else:
                return 'expired', privilege
        except Exception as e:
            sync_logger.error(f"Error parsing date: {privilege['activeUntil']}, error: {str(e)}")
            return 'expired', privilege
            
    return 'missing', None

async def syncRole(member: discord.Member, role_id: int, privilege_id: int) -> bool:
    """
    Синхронизация роли в Discord с привилегией на сервере
    
    Args:
        member: Объект участника Discord
        role_id: ID роли Discord
        privilege_id: ID привилегии
        
    Returns:
        bool: True если нужно закончить проверки ролей, False если проверять следующую
    """
    sync_logger.info(f'[SyncRole: {member.id} ({member.name})]: Start')
    
    try:
        user = await _retry_api_call(
            lambda: Vortex.GetDiscordUser(member.id)
        )
        if not user:
            sync_logger.info(f'[SyncRole: {member.id}]: User not linked to Steam')
            return True
            
        steam_id = user['user']['steamId']
        
        privileges = await _retry_api_call(
            lambda: Vortex.GetUserPrivileges(steam_id)
        )
        
        role_name = ""
        
        if privilege_id == Vortex.PrivilegeTypeId.Vip:
            role_name = "VIP"
        elif privilege_id == Vortex.PrivilegeTypeId.Premium:
            role_name = "Premium"
        elif privilege_id == Vortex.PrivilegeTypeId.Legend:
            role_name = "Legend"
        
        privilege_status, privilege = await check_privilege_status(privileges, privilege_id)
        has_role = hasRole(member, role_id)
        
        sync_logger.info(f'[SyncRole: {member.id}]: {role_name} privilege status: {privilege_status}, has role: {has_role}')
        
        if privilege_status == 'active' and has_role:
            sync_logger.info(f'[SyncRole: {member.id}]: User has active {role_name} privilege and role - nothing to do')
            return False
            
        if privilege_status in ['expired', 'active'] and not has_role:
            sync_logger.info(f'[SyncRole: {member.id}]: User has {role_name} privilege but not role - removing privilege')
            await _retry_api_call(
                lambda: Vortex.DeleteUserPrivilege(steam_id, privilege)
            )
            sync_logger.info(f'[SyncRole: {member.id}]: Successfully removed {role_name} privilege from API')
            return False
            
        if privilege_status == 'expired' and has_role:
            sync_logger.info(f'[SyncRole: {member.id}]: User has expired {role_name} privilege and has role - refreshing privilege')
            await _retry_api_call(
                lambda: Vortex.DeleteUserPrivilege(steam_id, privilege)
            )
            sync_logger.info(f'[SyncRole: {member.id}]: Deleted expired {role_name} privilege')
            
            await _retry_api_call(
                lambda: Vortex.SetUserPrivilege(steam_id, privilege_id)
            )
            sync_logger.info(f'[SyncRole: {member.id}]: Successfully added fresh {role_name} privilege to API')
            return False
            
        if privilege_status == 'missing' and has_role:
            sync_logger.info(f'[SyncRole: {member.id}]: Adding {role_name} privilege to API')
            await _retry_api_call(
                lambda: Vortex.SetUserPrivilege(steam_id, privilege_id)
            )
            sync_logger.info(f'[SyncRole: {member.id}]: Successfully added {role_name} privilege to API')
            return False
            
        sync_logger.info(f'[SyncRole: {member.id}]: {role_name} privilege not needed - skipping')
        return False
        
    except Exception as e:
        sync_logger.error(f'[SyncRole: {member.id}]: Error: {str(e)}')
        return True

async def syncAllRoles(member: discord.Member | discord.User) -> None:
    """
    Синхронизирует все роли пользователя
    
    Args:
        member: Объект участника Discord
    """
    if not isinstance(member, discord.Member):
        return
        
    try:
        sync_logger.info(f'Starting role sync for {member.id} ({member.name})')
        
        if await syncRole(member, settings.Preferences['vip_role_id'], Vortex.PrivilegeTypeId.Vip) or \
           await syncRole(member, settings.Preferences['premium_role_id'], Vortex.PrivilegeTypeId.Premium) or \
           await syncRole(member, settings.Preferences['legend_role_id'], Vortex.PrivilegeTypeId.Legend):
            return

        if 'linked_roles' in settings.Preferences:
            for primary_role_id, secondary_role_id in settings.Preferences['linked_roles'].items():
                if hasRole(member, int(primary_role_id)):
                    secondary_role = member.guild.get_role(secondary_role_id)
                    if secondary_role and secondary_role not in member.roles:
                        await member.add_roles(
                            secondary_role,
                            reason="Автоматическая выдача связанной роли при синхронизации"
                        )
                        sync_logger.info(
                            f'Added linked role {secondary_role_id} to '
                            f'user {member.id} during sync'
                        )
        
        sync_logger.info(f'Completed role sync for {member.id} ({member.name})')

    except Exception as e:
        sync_logger.error(f'Error syncing roles for {member.id}: {str(e)}')

async def tryGetOtherUser(
    user: discord.User | discord.Member,
    interaction: discord.Interaction
) -> Optional[Vortex.User]:
    """
    Функция пытается найти связанного пользователя Discord через API.
    
    Args:
        user: Объект пользователя Discord
        interaction: Объект взаимодействия Discord
        
    Returns:
        Optional[Vortex.User]: Данные пользователя или None если не найден
    """
    logger.info(f'Attempt to find user {user.id} ({user.name})')
    try:
        link = await _retry_api_call(
            lambda: Vortex.GetDiscordUser(user.id)
        )
        if not link:
            await interaction.response.send_message(
                content='Пользователь не привязал аккаунт',
                ephemeral=True
            )
            logger.info(f'User not found')
            return None
            
        logger.info(f'User found: {link["user"]["steamId"]}')
        return link['user']
    except Exception as e:
        logger.error(f'Error getting other user: {str(e)}')
        await interaction.response.send_message(
            content='Произошла ошибка при поиске аккаунта. Попробуйте позже.',
            ephemeral=True
        )
        return None

class ShareView(discord.ui.View):
    """Представление для кнопки 'Поделиться'"""
    
    def __init__(
        self,
        output: str,
        embed: Optional[discord.Embed] = None,
        channel: Optional[discord.TextChannel] = None,
        *,
        timeout: Optional[float] = 180
    ):
        super().__init__(timeout=timeout)
        self.output = output
        self.embed = embed
        self.channel = channel
        if self.channel:
            self.share.label = f'Поделиться в:  #[{self.channel.name}]'
    
    @discord.ui.button(label='Поделиться', style=discord.ButtonStyle.primary)
    async def share(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ) -> None:
        """Обработчик нажатия кнопки"""
        logger.info(f'Share button pressed {interaction.user.id} ({interaction.user.name})')
        try:
            if self.channel:
                await self.channel.send(self.output, embed=self.embed, silent=True)
            else:
                await interaction.channel.send(self.output, embed=self.embed)
            await interaction.response.edit_message(view=None)
        except Exception as e:
            logger.error(f'Error in share button: {str(e)}')
            await interaction.response.send_message(
                'Произошла ошибка при отправке сообщения',
                ephemeral=True
            )

def UserHasRole(member: discord.Member | discord.User, role_name: str) -> bool:
    """
    Проверяет наличие роли у пользователя
    
    Args:
        member: Объект участника Discord
        role_name: Имя роли
        
    Returns:
        bool: True если роль найдена, иначе False
    """
    if not isinstance(member, discord.Member):
        return False
    if not settings.IsRoleExists(role_name):
        return False
    return settings.Preferences[role_name] in [i.id for i in member.roles]

def createEmbedFromSteam(
    summary: Steam.PlayerSummary,
    title: str,
    description: Optional[str] = None
) -> discord.Embed:
    """
    Создает Discord Embed из данных Steam
    
    Args:
        summary: Данные профиля Steam
        title: Заголовок для Embed
        description: Описание для Embed
        
    Returns:
        discord.Embed: Созданный объект Embed
    """
    embed = discord.Embed(
        color=discord.Color.blurple(),
        title=title
    )
    if description:
        embed.description = description
    embed.set_author(
        name=summary['personaname'],
        url=summary['profileurl'],
        icon_url=summary['avatar']
    )
    return embed