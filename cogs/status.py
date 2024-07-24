import discord
import settings
from discord import app_commands
from discord.ext import commands
from ui.balance import SendWallet

logger = settings.logging.getLogger('discord')

class StatusCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='status', description='Отобразить информацию о вашем аккаунте')
    async def status(self, interaction: discord.Interaction):
        logger.info(f'Status (wallet) command called by {interaction.user.id} ({interaction.user.name})')
        await SendWallet(interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(StatusCommand(bot), guild=discord.Object(id = settings.GUILD_ID))