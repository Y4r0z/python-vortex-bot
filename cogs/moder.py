import datetime
import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.text import formatCoins
from tools.ds import tryGetOtherUser, ShareView, UserHasRole
import lib.vortex_api as Vortex
from typing import Optional, Dict, Any, List

logger = settings.logging.getLogger('discord')

def GetProfileEmbed(info: Vortex.BulkProfileInfo, playtime: Optional[Vortex.PlaytimeInfo] = None) -> discord.Embed:
    try:
        rank = info['rank'] if info['rank'] is not None else 'Отсутствует'
        
        playtime_str = ''
        if playtime:
            hours = playtime['total_hours']
            playtime_str = f'\nВремя игры: {hours:,} ч.'
        
        description = f'Ранг: {rank}{playtime_str}\nБаланс: {formatCoins(info["balance"])}\nSteam ID: {info["steamInfo"]["steamid"]}'
        perks = \
f"""
**Перки выжившего**:
1. {info['perks']['survivorPerk1']}
2. {info['perks']['survivorPerk2']}
3. {info['perks']['survivorPerk3']}
4. {info['perks']['survivorPerk4']}
**Перки зараженного**:
{info['perks']['boomerPerk']}
{info['perks']['smokerPerk']}
{info['perks']['hunterPerk']}
{info['perks']['jockeyPerk']}
{info['perks']['spitterPerk']}
{info['perks']['chargerPerk']}
{info['perks']['tankPerk']}
""" if info['perks'] else 'Отсутствуют'

        privileges = ('\n'.join(
            [f"{i['privilege']['name']} ({i['privilege']['description']}) - до {i['activeUntil'].replace('T', ' ')} UTC" \
                for i in info['privileges']]
        )) if len(info['privileges']) > 0 else 'Отсутствуют'

        embed = discord.Embed(
            color=discord.Color.dark_teal(),
            title='Информация об игроке',
            description=description,
        )
        embed.set_author(
            name=info['steamInfo']['personaname'],
            url=info['steamInfo']['profileurl'],
            icon_url=info['steamInfo']['avatarmedium']
        )
        embed.add_field(name='', value=perks, inline=False)
        embed.add_field(name='Привилегии', value=privileges, inline=False)
        return embed
    except Exception as e:
        logger.error(f"Error creating profile embed: {str(e)}")
        raise

def GetStatisticsEmbed(stats: Vortex.GameStatistics, steam_info: dict) -> discord.Embed:
    try:
        last_online = 'Неизвестно'
        if stats['last_online']:
            try:
                dt = datetime.datetime.fromisoformat(stats['last_online'].replace('Z', '+00:00'))
                last_online = dt.strftime('%d.%m.%y - %H:%M')
            except:
                last_online = stats['last_online']
        
        location = []
        if stats['last_country']: location.append(stats['last_country'])
        if stats['last_region']: location.append(stats['last_region'])
        if stats['last_city']: location.append(stats['last_city'])
        location_str = ', '.join(location) if location else 'Неизвестно'
        
        embed = discord.Embed(
            color=discord.Color.orange(),
            title='Последняя статистика',
            description=f'Последний ник: {stats["last_nickname"] or "Неизвестно"}\nОнлайн в: {last_online}'
        )
        embed.set_author(
            name=steam_info['personaname'],
            url=steam_info['profileurl'],
            icon_url=steam_info['avatarmedium']
        )
        embed.add_field(name='Местоположение', value=location_str, inline=False)
        embed.add_field(name='Последний IP', value=stats["last_ip"] or 'Неизвестно', inline=False)
        
        return embed
    except Exception as e:
        logger.error(f"Error creating statistics embed: {str(e)}")
        raise

def logToStr(log: Vortex.ChatLog, 
            bsteam_id: bool = False, 
            btime: bool = False, 
            bserver: bool = False, 
            bteam: bool = False) -> str:
    try:
        team_map = {
            3: 'зар.',
            2: 'выж.',
            1: 'набл.',
        }
        team = team_map.get(log['team'], '')
        
        chatTeam = '(команде)' if log['chatTeam'] == 1 else ''
        teamStr = f' [{team} ({chatTeam})]' if bteam else ''
        
        time = datetime.datetime.fromisoformat(log['time'])
        timeStr = f"[{time.strftime('%d.%m.%y - %H:%M')}]" if btime else ''
        
        serverStr = f'<{log["server"]}> ' if bserver else ''
        steam_id = f' (*{log["steamId"]}*)' if bsteam_id else ''
        servTimeStr = f'{serverStr} {timeStr}' if bserver or btime else ''
        
        return f'**{log["nickname"]}** {chatTeam}:  {log["text"]}\n-# {steam_id}  {servTimeStr}'
    except Exception as e:
        logger.error(f"Error formatting chat log: {str(e)}")
        raise

class ProfileView(discord.ui.View):
    def __init__(self, vortex_embed: discord.Embed, gamer_embed: discord.Embed, share_text: str):
        super().__init__(timeout=300)
        self.vortex_embed = vortex_embed
        self.gamer_embed = gamer_embed
        self.share_text = share_text
        self.current_page = 'vortex'
        self._update_button_styles()
    
    def _update_button_styles(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if item.label == 'Vortex':
                    item.style = discord.ButtonStyle.primary if self.current_page == 'vortex' else discord.ButtonStyle.secondary
                elif item.label == 'Gamer':
                    item.style = discord.ButtonStyle.primary if self.current_page == 'gamer' else discord.ButtonStyle.secondary
    
    @discord.ui.button(label='Vortex', style=discord.ButtonStyle.primary)
    async def vortex_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            self.current_page = 'vortex'
            self._update_button_styles()
            await interaction.response.edit_message(embed=self.vortex_embed, view=self)
        except Exception as e:
            logger.error(f'Error switching to Vortex page: {str(e)}')
    
    @discord.ui.button(label='Gamer', style=discord.ButtonStyle.secondary)
    async def gamer_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            self.current_page = 'gamer'
            self._update_button_styles()
            await interaction.response.edit_message(embed=self.gamer_embed, view=self)
        except Exception as e:
            logger.error(f'Error switching to Gamer page: {str(e)}')
    
    @discord.ui.button(label='Поделиться', style=discord.ButtonStyle.success)
    async def share(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            current_embed = self.vortex_embed if self.current_page == 'vortex' else self.gamer_embed
            await interaction.channel.send(self.share_text, embed=current_embed)
            await interaction.response.edit_message(view=None)
        except Exception as e:
            logger.error(f'Error in share button: {str(e)}')
            await interaction.response.send_message(
                'Произошла ошибка при отправке сообщения',
                ephemeral=True
            )

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
        target: Optional[discord.Member] = None,
        nickname: Optional[str] = None,
        text: Optional[str] = None,
        steam_id: Optional[str] = None,
        server: Optional[str] = None,
        limit: int = 15,
        offset: int = 0
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Chatlogs command called by {interaction.user.id} ({interaction.user.name})')
        
        try:
            if not UserHasRole(interaction.user, settings.RoleNames.Moder):
                await interaction.followup.send('У вас недостаточно прав.', ephemeral=True)
                return

            offset = min(1000, max(0, offset))
            limit = min(100, max(1, limit))

            if target:
                user = await tryGetOtherUser(target, interaction)
                if not user:
                    await interaction.followup.send('Не удалось получить информацию о пользователе.', ephemeral=True)
                    return
                steam_id = user['steamId']

            logs = await Vortex.GetLogs(text, steam_id, nickname, server, offset, limit)
            result = '\n'.join([logToStr(i, True, True, True, True) for i in logs])
            result = '(Логи не найдены)' if len(logs) == 0 else result if len(result) < 1930 else f"{result[:1930]}..."
            
            view = ShareView(output=f'{interaction.user.mention} поделился логами чата:\n{result}')
            await interaction.followup.send(result, view=view, ephemeral=True)

        except Exception as ex:
            logger.error(f'Error in chatlogs command: {str(ex)}')
            await interaction.followup.send(
                'Произошла ошибка при получении логов чата. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )
    
    @app_commands.command(name='getinfo', description='Получить информацию о пользователе')
    @discord.app_commands.describe(
        user='Пользователь, который привязал свой аккаунт',
        steam_id='Steam ID игрока'
    )
    async def get_info(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        steam_id: Optional[str] = None
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Get Info command called by {interaction.user.id} ({interaction.user.name})')
        
        try:
            if not UserHasRole(interaction.user, settings.RoleNames.Moder):
                await interaction.followup.send('У вас недостаточно прав.', ephemeral=True)
                return

            if user is None and steam_id is None:
                await interaction.followup.send('Не указан пользователь или Steam ID.', ephemeral=True)
                return

            if user:
                vortex_user = await tryGetOtherUser(user, interaction)
                if not vortex_user:
                    await interaction.followup.send('Пользователь не связал свой аккаунт', ephemeral=True)
                    return
                steam_id = vortex_user['steamId']

            target_steam_id = steam_id or ''
            
            vortex_info = await Vortex.GetBulkProfile(target_steam_id)
            
            playtime_info = None
            try:
                playtime_info = await Vortex.GetPlaytime(target_steam_id)
            except Exception as e:
                logger.warning(f'Failed to get playtime for {target_steam_id}: {str(e)}')
            
            vortex_embed = GetProfileEmbed(vortex_info, playtime_info)
            
            try:
                gamer_stats = await Vortex.GetBaseStatistics(target_steam_id)
                gamer_embed = GetStatisticsEmbed(gamer_stats, vortex_info['steamInfo'])
            except Exception as e:
                logger.warning(f'Failed to get statistics for {target_steam_id}: {str(e)}')
                gamer_embed = discord.Embed(
                    color=discord.Color.red(),
                    title='Игровая статистика',
                    description='Статистика недоступна'
                )
                gamer_embed.set_author(
                    name=vortex_info['steamInfo']['personaname'],
                    url=vortex_info['steamInfo']['profileurl'],
                    icon_url=vortex_info['steamInfo']['avatarmedium']
                )
            
            share_text = f'{interaction.user.mention} поделился информацией об игроке:'
            view = ProfileView(vortex_embed, gamer_embed, share_text)
            
            await interaction.followup.send(embed=vortex_embed, ephemeral=True, view=view)

        except Exception as ex:
            logger.error(f'Error in getinfo command: {str(ex)}')
            await interaction.followup.send(
                'Произошла ошибка при получении информации об игроке. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerCommands(bot), guild=discord.Object(id=settings.GUILD_ID))