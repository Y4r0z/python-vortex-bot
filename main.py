import settings
import discord
from discord.ext import commands
from ui.steam_link import LinkView
import lib.vortex_api as Vortex
from ui.setup import SetupView
from ui.balance import SendWallet

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
    
async def tryGetUser(interaction: discord.Interaction) -> Vortex.User | None:
    try:
        link = await Vortex.GetDiscordUser(interaction.user.id)
    except:
        await interaction.response.send_message(content='Вы не привязали ваш аккаунт к Steam, используйте команду `/link`, чтобы сделать это.', ephemeral=True)
        return None
    return link['user']

async def checkAdmin(interaction: discord.Interaction):
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
        # Если одна роль изменна, то остальные не трогать. Использую особенность "ленивых" выражений в python
        

    @bot.tree.command(name='setup', description='Настраивает бота в данном канале')
    @commands.has_permissions(administrator=True)
    async def setupcommand(interaction: discord.Interaction):
        if not (await checkAdmin(interaction)): return
        view = SetupView()
        await interaction.response.send_message(content='Настройка бота', view=view, ephemeral=True)
    
    @bot.tree.command(name='link', description='Привязать ваш Steam аккаунт к Discord')
    async def linkcommand(interaction: discord.Interaction):
        view = LinkView()
        await interaction.response.send_message(content='Нажмите, чтобы привязать ваш Steam аккаунт.', view=view, ephemeral=True)
    
    @bot.tree.command(name='balance', description='Показывает, сколько коинов у вас на счету')
    async def balance(interaction: discord.Interaction):
        user = await tryGetUser(interaction)
        if user is None: return
        balance = await Vortex.GetBalance(user['steamId'])
        await interaction.response.send_message(content=f'Ваш баланс: {balance['value']}', ephemeral=True)
    
    @bot.tree.command(name='pay', description='Передать коины другому пользователю')
    @discord.app_commands.describe(target="Пользователь, которому вы передаете коины", value="Сколько коинов передать")
    async def balance(interaction: discord.Interaction, target: discord.Member, value: int):
        if target.id == interaction.user.id:
            await interaction.response.send_message(content='Мы не можете передавать коины самому себе!', ephemeral=True)
            return
        user = await tryGetUser(interaction)
        if user is None: return
        try:
            user2 = await Vortex.GetDiscordUser(target.id)
        except:
            await interaction.response.send_message(content=f'Пользователь {target.mention} еще не связал свой аккаунт.', ephemeral=True)
            return
        balance = await Vortex.GetBalance(user['steamId'])
        if value > balance['value']: interaction.response.send_message(content='У вас не хватет коинов для передачи.', ephemeral=True)
        try:
            transaction = await Vortex.PayBalance(user['steamId'], user2['user']['steamId'], value)
        except: interaction.response.send_message(content='Не удалось передать коины.', ephemeral=True)
        await interaction.response.send_message(
            content=f'Вы передали коины в количестве {value} ед. игроку {target.mention}.\nОстаток на балансе: {transaction["source"]["value"]}', 
            ephemeral=True)
    
    @bot.tree.command(name='wallet', description='Отобразить информацию о вашем кошельке')
    async def wallet(interaction: discord.Interaction):
        await SendWallet(interaction)

    bot.run(settings.DISCORD_TOKEN)


if __name__ == '__main__':
    main()