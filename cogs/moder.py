import datetime
import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.text import formatCoins
from tools.ds import tryGetOtherUser, ShareView, UserHasRole
import lib.vortex_api as Vortex


logger = settings.logging.getLogger('discord')

def GetProfileEmbed(info: Vortex.BulkProfileInfo):
    rank = info['rank'] if info['rank'] is not None else 'Отсутствует'
    perks = \
f"""
**Перки выжившего**:
1. {info['perks']['survivorPerk1']}
2. {info['perks']['survivorPerk2']}
3. {info['perks']['survivorPerk3']}
4. {info['perks']['survivorPerk4']}
**Перки зараженного**:
Толстяк: {info['perks']['boomerPerk']}
Курилщик: {info['perks']['smokerPerk']}
Охотник: {info['perks']['hunterPerk']}
Жокей: {info['perks']['jockeyPerk']}
Плевальщица: {info['perks']['spitterPerk']}
Громила: {info['perks']['chargerPerk']}
Танк: {info['perks']['tankPerk']}
""" if info['perks'] else 'Отсутствуют'
    privileges = ('\n'.join(
        [f"{i['privilege']['name']} ({i['privilege']['description']}) - до {i['activeUntil'].replace('T', ' ')} UTC" \
            for i in info['privileges']]
    )) if len(info['privileges']) > 0 else 'Отсутствуют'
    embed = discord.Embed(
        color=discord.Color.dark_teal(),
        title='Информация об игроке',
        description=f'Ранг: {rank}\nБаланс: {formatCoins(info["balance"])}'
    )
    embed.set_author(
        name=info['steamInfo']['personaname'],
        url=info['steamInfo']['profileurl'],
        icon_url=info['steamInfo']['avatarmedium']
    )
    embed.add_field(
        name='Перки', value=perks, inline=False
    )
    embed.add_field(
        name='Привилегии', value=privileges, inline=False
    )
    return embed


def logToStr(log: Vortex.ChatLog, bsteam_id = False, btime = False, bserver = False, bteam = False):
    match(log['team']):
        case 3:
            team = 'зар.'
        case 2:
            team = 'выж.'
        case 1:
            team = 'набл.'
        case _:
            team = ''
    chatTeam = '(команде)' if log['chatTeam'] == 1 else ''
    teamStr = f' [{team} ({chatTeam})]' if bteam else ''
    time = datetime.datetime.fromisoformat(log['time'])
    timeStr = f"({time.strftime('%d.%m.%Y %H:%M:%S')})" if btime else ''
    serverStr = f'<{log["server"]}> ' if bserver else ''
    steam_id = f' ({log["steamId"]})' if bsteam_id else ''
    servTimeStr = f' -  *{serverStr} {timeStr}*' if bserver or btime else ''
    return f'**{log['nickname']}**{steam_id}{teamStr}:  {log['text']} {servTimeStr}'

class ModerCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='chatlogs', description='Получить последние логи чата')
    @discord.app_commands.rename(
        target='user',
        nickname='nickname',
        text='text',
        steam_id='steam_id',
        server='server',
        limit='count',
        offset='offset'
    )
    @discord.app_commands.describe(
        target='Пользователь, если тот связал свой аккаунт',
        nickname='Никнейм игрока',
        text='Текст сообщения в чате',
        steam_id='Steam ID игрока',
        server='Название сервера',
        limit='Количество логов в выдаче',
        offset='Смещение от начала выдачи'
    )
    async def chat_logs(
        self, 
        interaction: discord.Interaction,
        target: discord.Member | None,
        nickname: str | None,
        text: str | None,
        steam_id: str | None,
        server: str | None,
        limit: int = 15,
        offset: int = 0
    ):
        logger.info(f'Chatlogs command called by {interaction.user.id} ({interaction.user.name})')
        if not UserHasRole(interaction.user, settings.RoleNames.Moder):
            await interaction.response.send_message('У вас недостаточно прав.', ephemeral=True)
            return
        offset = min(1000, max(0, offset))
        limit = min(100, max(1, limit))
        if target:
           user = (await tryGetOtherUser(target, interaction))
           if not user: return
           steam_id = user['steamId']
        try:
            logs = await Vortex.GetLogs(
                text, steam_id, nickname, server, offset, limit)
        except Exception as ex:
            await interaction.response.send_message('Ошибка получения логов чата.', ephemeral=True)
            logger.error(ex)
            return
        result = '\n'.join([logToStr(i, False, True, True, False) for i in logs])
        result = '(Логи не найдены)' if len(logs) == 0 else result if len(result) < 2000 else result[:2000]
        view = ShareView(output=f'{interaction.user.mention} поделился логами чата:\n{result}')
        await interaction.response.send_message(result, view=view, ephemeral=True)
    
    @app_commands.command(name='getinfo', description='Получить информацию о пользователе')
    @discord.app_commands.describe(user='Пользователь, который привязал свой аккаунт', steam_id='Steam ID игрока')
    async def get_info(self, interaction: discord.Interaction, user: discord.Member | None, steam_id: str | None):
        logger.info(f'Get Info command called by {interaction.user.id} ({interaction.user.name})')
        if not UserHasRole(interaction.user, settings.RoleNames.Moder):
            await interaction.response.send_message('У вас недостаточно прав.', ephemeral=True)
            return
        if user is None and steam_id is None:
            await interaction.response.send_message('Не указан пользователь.', ephemeral=True)
            return
        if user:
            vortex_user = await tryGetOtherUser(user, interaction)
            if not vortex_user:
                await interaction.response.send_message('Пользователь не связал свой аккаунт', ephemeral=True)
                return
            steam_id = vortex_user['steamId']    
        try:
            info = await Vortex.GetBulkProfile(steam_id or '')
        except Exception as ex:
            logger.error(ex)
            await interaction.response.send_message('Ошибка получения информации об игроке.', ephemeral=True)
            return
        embed = GetProfileEmbed(info)
        view = ShareView(f'{interaction.user.mention} поделился информацией об игроке:', embed=embed)
        await interaction.response.send_message(embed=embed, ephemeral=True, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerCommands(bot), guild=discord.Object(id = settings.GUILD_ID))