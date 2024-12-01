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

    @app_commands.command(name='setup', description='Настраивает выдачу ролей ботом')
    @commands.has_permissions(administrator=True)
    async def setupcommand(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Setup command called by {interaction.user.id} ({interaction.user.name})')

        try:
            # Проверка на права администратора
            if not (await checkAdmin(interaction)):
                return

            # Создаем view для настройки
            try:
                view = SetupView()
            except Exception as e:
                logger.error(f'Error creating setup view: {str(e)}')
                await interaction.followup.send(
                    'Произошла ошибка при создании меню настройки. Пожалуйста, попробуйте позже.',
                    ephemeral=True
                )
                return

            # Определяем статус настройки
            text = ('Бот уже настроен. Вы можете спокойно отменить данное действие.'
                   if settings.IsSetUp() 
                   else 'Бот не настроен, обязательно выберите все роли.')

            # Отправляем меню настройки
            await interaction.followup.send(
                content=text,
                view=view,
                ephemeral=True
            )
            logger.info(f'Setup menu sent successfully')

        except Exception as e:
            logger.error(f'Error in setup command: {str(e)}')
            await interaction.followup.send(
                'Произошла непредвиденная ошибка при настройке бота. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCommand(bot), guild=discord.Object(id=settings.GUILD_ID))