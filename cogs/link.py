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
    async def linkcommand(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Link command called by {interaction.user.id} ({interaction.user.name})')

        try:
            if not settings.IsSetUp():
                await interaction.followup.send('Бот еще не настроен! Сообщите администратору сервера.')
                return

            try:
                user = await GetDiscordUser(interaction.user.id)
                if user:
                    await interaction.followup.send('Вы уже привязали свой аккаунт', ephemeral=True)
                    return
            except Exception as e:
                logger.debug(f'Expected error checking user link status: {str(e)}')
                pass

            view = LinkView()
            await interaction.followup.send(
                content='Нажмите, чтобы привязать ваш Steam аккаунт.',
                view=view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f'Error in link command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при попытке привязки аккаунта. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(LinkCommand(bot), guild=discord.Object(id=settings.GUILD_ID))