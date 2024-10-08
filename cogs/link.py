import discord
from lib.vortex_api import GetDiscordUser
import settings
from discord import app_commands
from discord.ext import commands
from ui.steam_link import LinkView
from tools.ds import syncRole

logger = settings.logging.getLogger('discord')


class LinkCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='link', description='Привязать ваш Steam аккаунт к Discord')
    async def linkcommand(self, interaction: discord.Interaction):
        logger.info(f'Link command called by {interaction.user.id} ({interaction.user.name})')
        if not settings.IsSetUp():
            await interaction.response.send_message(f'Бот еще не настроен! Сообщите администратору сервера.')
        try:
            await GetDiscordUser(interaction.user.id)
            await interaction.response.send_message('Вы уже привязали свой аккаунт', ephemeral=True)
            return          
        except:
            pass
        view = LinkView()
        await interaction.response.send_message(
            content='Нажмите, чтобы привязать ваш Steam аккаунт.', 
            view=view, 
            ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(LinkCommand(bot), guild=discord.Object(id = settings.GUILD_ID))