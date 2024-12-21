import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.text import formatCoins
from tools.ds import tryGetUser, ShareView, _retry_api_call
import lib.vortex_api as Vortex
from typing import Dict, Optional
from datetime import datetime, timedelta
import asyncio

logger = settings.logging.getLogger('discord')

class BalanceCache:
    """Кэш для хранения балансов пользователей"""
    def __init__(self, ttl_seconds: int = 60):
        self.cache: Dict[str, tuple[float, int]] = {}  # steamId -> (timestamp, balance)
        self.ttl = ttl_seconds
        self._lock = asyncio.Lock()
        
    async def get(self, steam_id: str) -> Optional[int]:
        """
        Получает баланс из кэша
        
        Args:
            steam_id: ID пользователя Steam
            
        Returns:
            Optional[int]: Баланс или None если не найден/устарел
        """
        async with self._lock:
            if steam_id not in self.cache:
                return None
                
            timestamp, balance = self.cache[steam_id]
            if datetime.now().timestamp() - timestamp > self.ttl:
                del self.cache[steam_id]
                return None
                
            return balance
            
    async def set(self, steam_id: str, balance: int) -> None:
        """
        Сохраняет баланс в кэш
        
        Args:
            steam_id: ID пользователя Steam
            balance: Баланс пользователя
        """
        async with self._lock:
            self.cache[steam_id] = (datetime.now().timestamp(), balance)

class BalanceCommand(commands.Cog):
    """Команда для просмотра баланса"""
    
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.balance_cache = BalanceCache()
        super().__init__()

    @app_commands.command(
        name='balance',
        description='Показывает, сколько коинов у вас на счету'
    )
    async def balance(self, interaction: discord.Interaction) -> None:
        """
        Показывает баланс пользователя
        
        Args:
            interaction: Объект взаимодействия Discord
        """
        await interaction.response.defer(ephemeral=True)
        
        logger.info(f'Balance command called by {interaction.user.id} ({interaction.user.name})')
        
        try:
            # Получаем данные пользователя
            user = await tryGetUser(interaction)
            if user is None:
                return
                
            steam_id = user['steamId']
            
            # Пробуем получить баланс из кэша
            cached_balance = await self.balance_cache.get(steam_id)
            if cached_balance is not None:
                logger.info(f'Using cached balance for {steam_id}')
                balance_value = cached_balance
            else:
                # Получаем актуальный баланс
                try:
                    balance = await _retry_api_call(
                        lambda: Vortex.GetBalance(steam_id)
                    )
                    balance_value = balance["value"]
                    
                    # Сохраняем в кэш
                    await self.balance_cache.set(steam_id, balance_value)
                    
                except Exception as e:
                    logger.error(f'Error getting balance: {str(e)}')
                    await interaction.followup.send(
                        'Произошла ошибка при получении баланса. Пожалуйста, попробуйте позже.',
                        ephemeral=True
                    )
                    return
            
            # Форматируем сообщение
            formatted_balance = formatCoins(balance_value)
            share_message = f'Баланс игрока {interaction.user.mention}: **{formatted_balance}**'
            
            # Создаем view для кнопки поделиться
            view = ShareView(share_message)
            
            # Отправляем ответ
            await interaction.followup.send(
                content=f'Ваш баланс: {formatted_balance}',
                ephemeral=True,
                view=view
            )
            
        except Exception as e:
            logger.error(f'Unexpected error in balance command: {str(e)}')
            await interaction.followup.send(
                'Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

async def setup(bot: commands.Bot) -> None:
    """
    Регистрирует команду в боте
    
    Args:
        bot: Объект бота Discord
    """
    await bot.add_cog(
        BalanceCommand(bot),
        guild=discord.Object(id=settings.GUILD_ID)
    )
