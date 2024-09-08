import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.ds import checkAdmin

logger = settings.logging.getLogger('discord')


def roleFromId(role_id: int):
    return [discord.SelectDefaultValue(id=role_id, type=discord.SelectDefaultValueType.role)]

class CommandsSetupView(discord.ui.View):
    def __init__(self, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.select_moder.default_values = roleFromId(settings.Preferences['moder_role_id']) \
            if settings.IsRoleExists('moder_role_id') else []
            
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Роль с доступом к модерским командам")
    async def select_moder(self, interaction: discord.Interaction, select_item: discord.ui.RoleSelect):
        settings.Preferences['moder_role_id'] = select_item.values[0].id
        await interaction.response.defer()


    @discord.ui.button(label='Подтвердить', style=discord.ButtonStyle.success)
    async def ok(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not settings.IsCommandsSetUp():
            await interaction.response.send_message('Не все роли выбраны!', ephemeral=True)
            return
        settings.SavePreferences()
        await interaction.response.edit_message(content='Настройки команд сохранены!', view=None)
    

    @discord.ui.button(label='Отмена', style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content='Сохранение настроек команд отменено!', view=None)



class CommandsSetupCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='setup_commands', description='Настраивает особые команды бота')
    @commands.has_permissions(administrator=True)
    async def setupcommand(self, interaction: discord.Interaction):
        if not (await checkAdmin(interaction)): return
        logger.info(f'Commands setup command called by {interaction.user.id} ({interaction.user.name})')
        view = CommandsSetupView()
        text = 'Бот уже настроен. Вы можете спокойно отменить данное действие.' if settings.IsCommandsSetUp() else 'Бот не настроен, обязательно выберите роли.'
        await interaction.response.send_message(content=text, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CommandsSetupCommand(bot), guild=discord.Object(id = settings.GUILD_ID))