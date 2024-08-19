import discord
import settings
from discord import app_commands
from discord.ext import commands
from ui.balance import BalanceShareView
from tools.text import formatCoins
from tools.ds import tryGetOtherUser, ShareView, UserHasRole, tryGetUser
import lib.vortex_api as Vortex


logger = settings.logging.getLogger('discord')

class AcceptBanView(discord.ui.View):
    def __init__(self, steam_id: str, duration: int, reason: str):
        super().__init__(timeout=180)
        self.steam_id = steam_id
        self.duration = duration
        self.reason = reason
    
    @discord.ui.button(label='Подтвердить', style=discord.ButtonStyle.danger)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await Vortex.SbBanPlayer(self.steam_id, self.duration, self.reason)
        except Vortex.UserAlreadyBannedError:
            await interaction.response.edit_message(content='Игрок уже забанен.', view=None)
            return
        except Vortex.UserNotFoundError:
            await interaction.response.edit_message(content='Игрок не найден.', view=None)
            return
        except:
            await interaction.response.edit_message(content='Неизвестная ошибка.', view=None)
            return
        await interaction.response.edit_message(content=f'Игрок ({self.steam_id}) забанен.', view=None)
    
    @discord.ui.button(label='Отмена', style=discord.ButtonStyle.primary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content=f'Бан игрока ({self.steam_id}) отменен.', view=None)


class SourcebansCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()
    
    @app_commands.command(name='ban', description='Банит игрока на серверах')
    async def ban(self, interaction: discord.Interaction, steam_id: str, reason: str, days: int, hours: int = 0, minutes: int = 0):
        logger.info(f'Ban command called by {interaction.user.id} ({interaction.user.name})')
        if not UserHasRole(interaction.user, settings.RoleNames.Moder):
            await interaction.response.send_message('У вас недостаточно прав.', ephemeral=True)
            return
        duration = (minutes * 60) + (hours * 3600) + (days * 86400)
        if duration < 60:
            await interaction.response.send_message('Минимальный период бана: 1 минута', ephemeral=True)
            return
        view = AcceptBanView(steam_id=steam_id, duration=duration, reason=reason)
        await interaction.response.send_message(
            f'Подтвердите бан игрока.\nSteam ID: {steam_id}\nПричина: {reason}\nДлительность (секунды): {duration}', ephemeral=True, view=view)
        
    
async def setup(bot: commands.Bot):
    await bot.add_cog(SourcebansCommands(bot), guild=discord.Object(id = settings.GUILD_ID))