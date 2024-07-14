import settings
import discord
from discord.ext import commands
from ui.steam_link import LinkView
import lib.vortex_api as Vortex
from ui.setup import SetupView
from ui.balance import SendWallet, PayWarnView, BalanceShareView
from tools.text import formatCoins

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
    
async def tryGetUser(interaction: discord.Interaction) -> Vortex.User | None:
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
    logger.info(f'Checking administrator flag for: {interaction.user.id} ({interaction.user.name})')
    if interaction.user.guild_permissions.administrator == False:
        await interaction.response.send_message('Данная команда может быть использована только администратором.', ephemeral=True)
        return False
    return True

def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    guild = discord.Object(id=settings.GUILD_ID)

    bot = commands.Bot(intents=intents, command_prefix='!')    

    @bot.event
    async def on_ready():
        logger.info('Bot started')
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        logger.info('Guild initialized')

    @bot.event
    async def on_member_update(before: discord.Member, after: discord.Member):
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
        

    @bot.tree.command(name='setup', description='Настраивает бота в данном канале')
    @commands.has_permissions(administrator=True)
    async def setupcommand(interaction: discord.Interaction):
        if not (await checkAdmin(interaction)): return
        logger.info(f'Setup command called by {interaction.user.id} ({interaction.user.name})')
        view = SetupView()
        await interaction.response.send_message(content='Настройка бота', view=view, ephemeral=True)
    
    @bot.tree.command(name='link', description='Привязать ваш Steam аккаунт к Discord')
    async def linkcommand(interaction: discord.Interaction):
        logger.info(f'Link command called by {interaction.user.id} ({interaction.user.name})')
        view = LinkView()
        await interaction.response.send_message(
            content='Нажмите, чтобы привязать ваш Steam аккаунт.', 
            view=view, 
            ephemeral=True)
    
    @bot.tree.command(name='balance', description='Показывает, сколько коинов у вас на счету')
    async def balance(interaction: discord.Interaction):
        logger.info(f'Balance command called by {interaction.user.id} ({interaction.user.name})')
        user = await tryGetUser(interaction)
        if user is None:
            logger.info(f'User not found)')
            return
        balance = await Vortex.GetBalance(user['steamId'])
        await interaction.response.send_message(content=f'Ваш баланс: {formatCoins(balance['value'])}', ephemeral=True, view=BalanceShareView(user=interaction.user, value=balance['value']))
    
    @bot.tree.command(name='pay', description='Передать коины другому пользователю')
    @discord.app_commands.describe(target="Пользователь, которому вы передаете коины", value="Сколько коинов передать")
    @discord.app_commands.rename(target='кому', value='сколько')
    async def balance(interaction: discord.Interaction, target: discord.Member, value: int):
        logger.info(f'Pay command called by {interaction.user.id} ({interaction.user.name})')
        if target.id == interaction.user.id:
            await interaction.response.send_message(content='Мы не можете передавать коины самому себе!', ephemeral=True)
            logger.info('User tried to pay himself: return')
            return
        if target.bot:
            await interaction.response.send_message(content='У бота нет кошелька! 😒', ephemeral=True)
            logger.info('User tried to pay bot: return')
            return
        user = await tryGetUser(interaction)
        if user is None:
            logger.info('User not found: return')
            return
        try:
            user2 = await Vortex.GetDiscordUser(target.id)
        except:
            logger.info('User not linked: return')
            await interaction.response.send_message(content=f'Пользователь {target.mention} еще не связал свой аккаунт.', ephemeral=True)
            return
        balance = await Vortex.GetBalance(user['steamId'])
        if value > balance['value']: 
            logger.info('User tried to pay more than he/she has: return')
            interaction.response.send_message(content='У вас не хватет коинов для передачи.', ephemeral=True)
            return
        try:
            transaction = await Vortex.PayBalance(user['steamId'], user2['user']['steamId'], value)
        except Exception as e: 
            logger.info(f'\nTransaction error:\n{str(e)}\n')
            interaction.response.send_message(content='Не удалось передать коины.', ephemeral=True)
            return
        view = PayWarnView(source=interaction.user, target=target, value=value)
        logger.info('Pay: success')
        await interaction.response.send_message(
            content=f'Вы передали {formatCoins(value)} игроку {target.mention}.\nОстаток на балансе: {formatCoins(transaction["source"]["value"])}', 
            ephemeral=True, view=view)
    
    @bot.tree.command(name='status', description='Отобразить информацию о вашем аккаунте')
    async def status(interaction: discord.Interaction):
        logger.info(f'Status (wallet) command called by {interaction.user.id} ({interaction.user.name})')
        await SendWallet(interaction)

    bot.run(settings.DISCORD_TOKEN, root_logger=True)


if __name__ == '__main__':
    main()