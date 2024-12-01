import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.text import formatCoins
from tools.ds import tryGetUser, ShareView
import lib.vortex_api as Vortex

logger = settings.logging.getLogger('discord')

class BalanceCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='balance', description='Показывает, сколько коинов у вас на счету')
    async def balance(self, interaction: discord.Interaction) -> None:  # добавил -> None и правильный импорт discord.Interaction
        await interaction.response.defer(ephemeral=True)
        
        logger.info(f'Balance command called by {interaction.user.id} ({interaction.user.name})')
        
        try:
            user = await tryGetUser(interaction)
            if user is None:
                await interaction.followup.send('Аккаунт не найден. Пожалуйста, привяжите ваш Steam аккаунт.')
                return
            
            balance = await Vortex.GetBalance(user['steamId'])
            view = ShareView(f'Баланс игрока {interaction.user.mention}: **{formatCoins(balance["value"])}**')
            await interaction.followup.send(
                content=f'Ваш баланс: {formatCoins(balance["value"])}',
                ephemeral=True,
                view=view
            )
            
        except Exception as e:
            logger.error(f'Error in balance command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при получении баланса. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(BalanceCommand(bot), guild=discord.Object(id = settings.GUILD_ID))