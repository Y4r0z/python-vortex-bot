import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.ds import checkAdmin
import typing

logger = settings.logging.getLogger('discord')


def channelFromId(channel_id: int):
    return [discord.SelectDefaultValue(id=channel_id, type=discord.SelectDefaultValueType.channel)]

class ChannelsSetupView(discord.ui.View):
    def __init__(self, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        values = settings.Get('bot_output_channel_id', [], channelFromId)
        self.select_output.default_values = values
        self.select_output.channel_types = [discord.ChannelType.text]
            
    @discord.ui.select(cls=discord.ui.ChannelSelect, placeholder="Канал в который будет отправлятся результат вывода некоторых команд")
    async def select_output(self, interaction: discord.Interaction, select_item: discord.ui.ChannelSelect):
        settings.Preferences['bot_output_channel_id'] = select_item.values[0].id
        await interaction.response.edit_message(view=self)


    @discord.ui.button(label='Подтвердить', style=discord.ButtonStyle.success)
    async def ok(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not settings.IsChannelsSetUp():
            await interaction.response.send_message('Не все каналы выбраны!', ephemeral=True)
            return
        settings.SavePreferences()
        await interaction.response.edit_message(content='Настройки каналов сохранены!', view=None)
    

    @discord.ui.button(label='Отмена', style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content='Сохранение настроек каналов отменено!', view=None)



class ChannelsSetupCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name='setup_channels', description='Настраивает каналы бота')
    @commands.has_permissions(administrator=True)
    async def setupcommand(self, interaction: discord.Interaction):
        if not (await checkAdmin(interaction)): return
        logger.info(f'Channels setup command called by {interaction.user.id} ({interaction.user.name})')
        view = ChannelsSetupView()
        text = 'Бот уже настроен. Вы можете спокойно отменить данное действие.' if settings.IsChannelsSetUp() else 'Бот не настроен, обязательно выберите каналы.'
        await interaction.response.send_message(content=text, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelsSetupCommand(bot), guild=discord.Object(id = settings.GUILD_ID))