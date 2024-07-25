import discord
import settings
from discord import app_commands
from discord.ext import commands
from ui.setup import SetupView
from tools.ds import checkAdmin

logger = settings.logging.getLogger('discord')


class SetupCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='setup', description='Настраивает бота в данном канале')
    @commands.has_permissions(administrator=True)
    async def setupcommand(self, interaction: discord.Interaction):
        if not (await checkAdmin(interaction)): return
        logger.info(f'Setup command called by {interaction.user.id} ({interaction.user.name})')
        view = SetupView()
        text = 'Бот уже настроен. Мы можете спокойно отменить данное действие.' if settings.IsSetUp() else 'Бот не настроен, обязательно выберите все роли.'
        await interaction.response.send_message(content=text, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCommand(bot), guild=discord.Object(id = settings.GUILD_ID))