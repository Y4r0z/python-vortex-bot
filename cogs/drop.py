import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.text import formatCoins
from tools.ds import tryGetUser, ShareView
import datetime
from datetime import timezone
import lib.vortex_api as Vortex

logger = settings.logging.getLogger('discord')

class DropShareView(discord.ui.View):
    def __init__(self, user: discord.Member | discord.User, value: int, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.user = user
        self.value = value
    
    @discord.ui.button(label='Поделиться', style=discord.ButtonStyle.blurple)
    async def share(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(view=None)
        if not isinstance(interaction.channel, discord.TextChannel): return
        await interaction.channel.send(f'Игроку {self.user.mention} выпало {formatCoins(self.value)} в `/drop`', silent=True)

class DropCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='drop', description='Бесплатно выдает коины')
    async def balance(self, interaction: discord.Interaction):
        logger.info(f'Drop command called by {interaction.user.id} ({interaction.user.name})')
        
        # Получаем текущее время в UTC
        current_utc = datetime.datetime.now(timezone.utc)
        # Создаем наивное время для сравнения
        current_naive = current_utc.replace(tzinfo=None)
        
        logger.info(f'Current UTC time: {current_utc.isoformat()}')
        
        user = await tryGetUser(interaction)
        if user is None:
            return
            
        try:
            # Получаем данные о дропе
            drop = await Vortex.GetMoneyDrop(user['steamId'])
            logger.info(f'Drop API response: {drop}')
            
            value = drop['value']
            next_drop_str = drop['nextDrop']
            
            # Парсим время следующего дропа (оно приходит без временной зоны)
            next_drop = datetime.datetime.fromisoformat(next_drop_str)
            
            # Логируем время для отладки
            logger.info(f'Next drop time: {next_drop.isoformat()}')
            logger.info(f'Time until next drop: {(next_drop - current_naive).total_seconds()} seconds')
            
            # Получаем timestamp для Discord timestamp formatting
            # Добавляем UTC для корректного timestamp
            next_drop_utc = next_drop.replace(tzinfo=timezone.utc)
            next_drop_timestamp = int(next_drop_utc.timestamp())
            
            # Проверяем, можно ли получить награду
            if value == 0:
                if current_naive < next_drop:
                    await interaction.response.send_message(
                        f'Вы уже получали коины! Вы можете забрать больше коинов <t:{next_drop_timestamp}:R>', 
                        ephemeral=True
                    )
                else:
                    # Если время прошло, но value = 0, возможно нужно обновить состояние
                    logger.warning(f'Drop time passed but value is 0. User: {user["steamId"]}, Next drop: {next_drop_str}')
                    await interaction.response.send_message(
                        'Пожалуйста, подождите несколько секунд и попробуйте снова.',
                        ephemeral=True
                    )
                return
            
            # Если есть награда для получения
            channel: discord.TextChannel = settings.Get('bot_output_channel_id', None, self.bot.get_channel)
            view = ShareView(
                f'Игроку {interaction.user.mention} выпало {formatCoins(value)} в `/drop`',
                channel=channel
            )
            
            await interaction.response.send_message(
                f'Вы получили {formatCoins(value)}. Вы можете забрать больше коинов <t:{next_drop_timestamp}:R>',
                ephemeral=True,
                view=view
            )
                
        except ValueError as e:
            logger.error(f'Error parsing time: {str(e)}')
            await interaction.response.send_message(
                'Произошла ошибка при обработке времени. Пожалуйста, сообщите администратору.',
                ephemeral=True
            )
        except Exception as e:
            logger.error(f'Unexpected error: {str(e)}')
            await interaction.response.send_message(
                'Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(DropCommand(bot), guild=discord.Object(id = settings.GUILD_ID))