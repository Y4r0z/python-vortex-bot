import discord
import settings
from discord import app_commands
from discord.ext import commands
from ui.balance import BalanceShareView
from tools.text import formatCoins
from tools.discord import tryGetUser
import lib.vortex_api as Vortex


logger = settings.logging.getLogger('discord')


class BalanceCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='balance', description='Показывает, сколько коинов у вас на счету')
    async def balance(self, interaction: discord.Interaction):
        logger.info(f'Balance command called by {interaction.user.id} ({interaction.user.name})')
        user = await tryGetUser(interaction)
        if user is None:
            logger.info(f'User not found)')
            return
        balance = await Vortex.GetBalance(user['steamId'])
        await interaction.response.send_message(
            content=f'Ваш баланс: {formatCoins(balance['value'])}', 
            ephemeral=True, 
            view=BalanceShareView(user=interaction.user, value=balance['value'])
        )
    
async def setup(bot: commands.Bot):
    await bot.add_cog(BalanceCommand(bot), guild=discord.Object(id = settings.GUILD_ID))