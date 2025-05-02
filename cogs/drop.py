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
    async def share(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.message.edit(view=None, content="Вы поделились информацией о полученных коинах!")
        if not isinstance(interaction.channel, discord.TextChannel): return
        await interaction.channel.send(f'Игроку {self.user.mention} выпало {formatCoins(self.value)} в `/drop`', silent=True)

class DropCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='drop', description='Бесплатно выдает коины')
    async def drop(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Drop command called by {interaction.user.id} ({interaction.user.name})')
        
        current_utc = datetime.datetime.now(timezone.utc)
        current_naive = current_utc.replace(tzinfo=None)
        
        logger.info(f'Current UTC time: {current_utc.isoformat()}')
        
        user = await tryGetUser(interaction)
        if user is None:
            await interaction.followup.send('Аккаунт не найден. Пожалуйста, привяжите ваш Steam аккаунт.')
            return
            
        try:
            drop = await Vortex.GetMoneyDrop(user['steamId'])
            logger.info(f'Drop API response: {drop}')
            
            value = drop['value']
            next_drop_str = drop['nextDrop']
            
            next_drop = datetime.datetime.fromisoformat(next_drop_str)
            
            logger.info(f'Next drop time: {next_drop.isoformat()}')
            logger.info(f'Time until next drop: {(next_drop - current_naive).total_seconds()} seconds')
            
            next_drop_utc = next_drop.replace(tzinfo=timezone.utc)
            next_drop_timestamp = int(next_drop_utc.timestamp())
            
            if value == 0:
                if current_naive < next_drop:
                    await interaction.followup.send(
                        f'Вы уже получали коины! Вы можете забрать больше коинов <t:{next_drop_timestamp}:R>', 
                        ephemeral=True
                    )
                else:
                    logger.warning(f'Drop time passed but value is 0. User: {user["steamId"]}, Next drop: {next_drop_str}')
                    await interaction.followup.send(
                        'Пожалуйста, подождите несколько секунд и попробуйте снова.',
                        ephemeral=True
                    )
                return
            
            channel: discord.TextChannel = settings.Get('bot_output_channel_id', None, self.bot.get_channel)
            view = ShareView(
                f'Игроку {interaction.user.mention} выпало {formatCoins(value)} в `/drop`',
                channel=channel
            )
            
            await interaction.followup.send(
                f'Вы получили {formatCoins(value)}. Вы можете забрать больше коинов <t:{next_drop_timestamp}:R>',
                ephemeral=True,
                view=view
            )
                
        except ValueError as e:
            logger.error(f'Error parsing time: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при обработке времени. Пожалуйста, сообщите администратору.',
                ephemeral=True
            )
        except Exception as e:
            logger.error(f'Unexpected error: {str(e)}')
            await interaction.followup.send(
                'Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(DropCommand(bot), guild=discord.Object(id = settings.GUILD_ID))