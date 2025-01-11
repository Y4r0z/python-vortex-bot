from discord.ext import commands, tasks
from discord import app_commands
import discord
from datetime import datetime, time, timedelta
import logging
import settings
from tools.ds import checkAdmin, _retry_api_call
import lib.vortex_api as Vortex
from typing import Optional, Dict, List, Any

class SeasonRewards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guild_id = int(settings.GUILD_ID)
        self.logger = settings.logging.getLogger('discord')
        self.season_task.start()
        
        # Награды за места
        self.rewards = {
            1: {"privilege": Vortex.PrivilegeTypeId.Legend, "coins": 100000},
            2: {"privilege": Vortex.PrivilegeTypeId.Premium, "coins": 50000},
            3: {"privilege": Vortex.PrivilegeTypeId.Vip, "coins": 25000}
        }
        
        # Иерархия привилегий
        self.privilege_hierarchy = [
            Vortex.PrivilegeTypeId.Vip,
            Vortex.PrivilegeTypeId.Premium,
            Vortex.PrivilegeTypeId.Legend
        ]

    def cog_unload(self):
        self.season_task.cancel()

    async def get_top_players(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получение топ игроков"""
        return await _retry_api_call(
            lambda: Vortex.GetScoreTop(limit=limit)
        )

    async def check_player_privileges(self, steam_id: str) -> Dict[str, bool]:
        """Проверка текущих привилегий игрока"""
        return await _retry_api_call(
            lambda: Vortex.GetPrivilegeSet(steam_id)
        )

    async def should_give_coins(self, steam_id: str, reward_privilege_id: int) -> bool:
        """Определяет, нужно ли выдавать коины вместо привилегии"""
        try:
            privileges = await self.check_player_privileges(steam_id)
            
            # Проверяем привилегии в порядке иерархии
            reward_index = self.privilege_hierarchy.index(reward_privilege_id)
            for privilege_id in self.privilege_hierarchy[reward_index:]:
                privilege_name = {
                    Vortex.PrivilegeTypeId.Legend: 'legend',
                    Vortex.PrivilegeTypeId.Premium: 'premium',
                    Vortex.PrivilegeTypeId.Vip: 'vip'
                }[privilege_id]
                if privileges.get(privilege_name, False):
                    return True  # У игрока есть привилегия того же или более высокого уровня
                    
            return False  # Нет привилегий выше или равных награде
            
        except Exception as e:
            self.logger.error(f"Error checking privileges for {steam_id}: {e}")
            return True  # В случае ошибки выдаем коины

    async def add_coins(self, steam_id: str, amount: int) -> None:
        """Начисление коинов игроку"""
        await _retry_api_call(
            lambda: Vortex.AddBalance(steam_id, amount)
        )

    async def give_privilege(self, steam_id: str, privilege_id: int) -> None:
        """Выдача привилегии игроку на месяц"""
        await _retry_api_call(
            lambda: Vortex.SetUserPrivilege(steam_id, privilege_id)
        )

    async def _give_reward(self, user_data: Dict[str, Any], place: int) -> Dict[str, Any]:
        """Выдача награды за место и возврат информации о награде"""
        try:
            steam_id = user_data['steamId']
            reward = self.rewards[place]
            
            # Проверяем, нужно ли выдавать коины
            give_coins = await self.should_give_coins(steam_id, reward['privilege'])
            
            if give_coins:
                await self.add_coins(steam_id, reward['coins'])
                reward_info = {
                    'type': 'coins',
                    'value': reward['coins']
                }
            else:
                await self.give_privilege(steam_id, reward['privilege'])
                # Получаем название привилегии для отображения
                privilege_names = {
                    Vortex.PrivilegeTypeId.Legend: 'LEGEND',
                    Vortex.PrivilegeTypeId.Premium: 'PREMIUM',
                    Vortex.PrivilegeTypeId.Vip: 'VIP'
                }
                reward_info = {
                    'type': 'privilege',
                    'value': privilege_names[reward['privilege']]
                }
            
            self.logger.info(f"Reward given to {steam_id}: {reward_info}")
            return reward_info
            
        except Exception as e:
            self.logger.error(f"Error giving reward to {steam_id}: {e}")
            return {'type': 'error', 'value': str(e)}

    async def announce_reward(self, user_data: Dict[str, Any], place: int, reward_info: Dict[str, Any]) -> None:
        """Объявление о выдаче награды"""
        channel_id = settings.Get('bot_rewards_channel_id', 0)
        if not channel_id:
            self.logger.warning("Rewards channel not set up")
            return
            
        channel = self.bot.get_channel(channel_id)
        if not channel:
            self.logger.error("Rewards channel not found")
            return
            
        steam_info = user_data.get('steamInfo', {})
        name = steam_info.get('personaname', 'Unknown')
        
        if reward_info['type'] == 'coins':
            coins_formatted = f"{reward_info['value']:,}".replace(',', ' ')
            reward_text = f"{coins_formatted} коинов"
        else:
            reward_text = f"привилегия {reward_info['value']} на 30 дней"
            
        embed = discord.Embed(
            title=f"🏆 Награда за {place} место",
            description=f"Игрок **{name}** получает {reward_text}!",
            color=discord.Color.gold()
        )
        
        await channel.send(embed=embed)

    async def announce_results(self, top_players: List[Dict[str, Any]]) -> None:
        """Объявление результатов сезона"""
        channel_id = settings.Get('bot_rewards_channel_id', 0)
        if not channel_id:
            self.logger.warning("Rewards channel not set up")
            return
            
        channel = self.bot.get_channel(channel_id)
        if not channel:
            self.logger.error("Rewards channel not found")
            return
            
        embed = discord.Embed(
            title="🏆 Итоги сезона",
            description="Поздравляем победителей!",
            color=discord.Color.gold()
        )
        
        for i, player in enumerate(top_players[:3], 1):
            steam_info = player.get('steamInfo', {})
            name = steam_info.get('personaname', 'Unknown')
            score = f"{player['score']:,}".replace(',', ' ')
            reward = self.rewards[i]
            
            # Проверяем, какую награду получит игрок
            give_coins = await self.should_give_coins(player['steamId'], reward['privilege'])
            coins_formatted = f"{reward['coins']:,}".replace(',', ' ')
            
            # Получаем название привилегии для отображения
            privilege_names = {
                Vortex.PrivilegeTypeId.Legend: 'LEGEND',
                Vortex.PrivilegeTypeId.Premium: 'PREMIUM',
                Vortex.PrivilegeTypeId.Vip: 'VIP'
            }
            reward_text = f"{coins_formatted} коинов" if give_coins else f"привилегия {privilege_names[reward['privilege']]}"
            
            embed.add_field(
                name=f"#{i} {name}",
                value=f"Очков: {score}\nНаграда: {reward_text}",
                inline=False
            )
        
        await channel.send(embed=embed)

    @tasks.loop(time=time(hour=0, minute=0))
    async def season_task(self):
        """Ежедневная проверка и подведение итогов сезона"""
        if datetime.now().day != 1:
            return
            
        self.logger.info("Starting season reset task")
        try:
            # Получаем топ игроков перед сбросом
            top_players = await self.get_top_players(limit=3)
            
            # Объявляем результаты
            await self.announce_results(top_players)
            
            # Выдаем награды топ-3 игрокам
            rewards_info = []
            for place, player in enumerate(top_players[:3], 1):
                reward_info = await self._give_reward(player, place)
                rewards_info.append(reward_info)
                await self.announce_reward(player, place, reward_info)
            
            # Сбрасываем сезон только после выдачи всех наград
            await _retry_api_call(
                lambda: Vortex._Post(f'{Vortex.host}/score/season/reset')
            )
                
        except Exception as e:
            self.logger.error(f"Error in season task: {str(e)}", exc_info=True)
            
            channel_id = settings.Get('bot_rewards_channel_id', 0)
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    await channel.send("❌ Произошла ошибка при подведении итогов сезона. Администраторы были уведомлены.")

    @app_commands.command(
        name='force_season_rewards',
        description='Принудительно выполнить выдачу наград за сезон'
    )
    @commands.has_permissions(administrator=True)
    async def force_rewards(self, interaction: discord.Interaction):
        """Команда для принудительного запуска выдачи наград"""
        await interaction.response.defer(ephemeral=True)
        try:
            if not (await checkAdmin(interaction)):
                return
                
            self.logger.info(f'Force season rewards called by {interaction.user.id} ({interaction.user.name})')
            
            # Получаем топ игроков
            top_players = await self.get_top_players(limit=3)
            
            # Объявляем результаты
            await self.announce_results(top_players)
            
            # Выдаем награды топ-3 игрокам
            rewards_info = []
            for place, player in enumerate(top_players[:3], 1):
                reward_info = await self._give_reward(player, place)
                rewards_info.append(reward_info)
                await self.announce_reward(player, place, reward_info)
            
            # Сбрасываем сезон только после выдачи всех наград
            await _retry_api_call(
                lambda: Vortex._Post(f'{Vortex.host}/score/season/reset')
            )
            
            # Проверяем, были ли ошибки при выдаче наград
            if any(reward.get('type') == 'error' for reward in rewards_info):
                await interaction.followup.send('⚠️ Награды выданы частично. Проверьте логи для деталей.', ephemeral=True)
            else:
                await interaction.followup.send('✅ Награды успешно выданы!', ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error in force_rewards command: {str(e)}", exc_info=True)
            await interaction.followup.send(
                "❌ Произошла ошибка при выдаче наград. Проверьте логи.",
                ephemeral=True
            )

    @app_commands.command(
        name='season_info',
        description='Показать информацию о текущем сезоне'
    )
    async def season_info(self, interaction: discord.Interaction):
        """Команда для просмотра информации о текущем сезоне"""
        try:
            top_players = await self.get_top_players(limit=10)
            
            embed = discord.Embed(
                title="📊 Текущий сезон",
                description="Топ-10 игроков:",
                color=discord.Color.blue()
            )
            
            for player in top_players:
                steam_info = player.get('steamInfo', {})
                name = steam_info.get('personaname', 'Unknown')
                score = f"{player['score']:,}".replace(',', ' ')
                embed.add_field(
                    name=f"#{player['rank']} {name}",
                    value=f"Очков: {score}",
                    inline=False
                )
                
            # Добавляем информацию о времени до конца сезона
            now = datetime.now()
            next_month = datetime(now.year + (now.month == 12), 
                                (now.month % 12) + 1, 
                                1)
            days_left = (next_month - now).days
            
            embed.set_footer(text=f"До конца сезона: {days_left} дней")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in season_info command: {e}")
            await interaction.response.send_message(
                "Произошла ошибка при получении информации о сезоне",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(SeasonRewards(bot), guild=discord.Object(id=settings.GUILD_ID))
