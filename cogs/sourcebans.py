import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.ds import tryGetOtherUser, ShareView, UserHasRole, tryGetUser, createEmbedFromSteam
import lib.vortex_api as Vortex
import lib.steam_api as Steam


logger = settings.logging.getLogger('discord')


class AcceptBanView(discord.ui.View):
    def __init__(self, summary: Steam.PlayerSummary, duration: int, reason: str):
        super().__init__(timeout=180)
        self.summary = summary
        self.duration = duration
        self.reason = reason
    
    @discord.ui.button(label='Подтвердить', style=discord.ButtonStyle.danger)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await Vortex.SbBanPlayer(self.summary['steamid'], self.duration, self.reason)
        except Vortex.UserAlreadyBannedError:
            await interaction.response.edit_message(view=None, embed=createEmbedFromSteam(self.summary, 'Игрок уже забанен'))
            return
        except Vortex.UserNotFoundError:
            await interaction.response.edit_message(view=None, embed=createEmbedFromSteam(self.summary, 'Игрок не найден'))
            return
        except Exception as e:
            await interaction.response.edit_message(view=None, embed=createEmbedFromSteam(self.summary, 'Неизвестная ошибка'))
            logger.error(f'Ban error: {e}')
            return
        embed = createEmbedFromSteam(self.summary, 'Игрок успешно забанен!',
                                     f'Причина: {self.reason}\nДлительность (секунды): {self.duration}')
        view = ShareView(embed=embed, output=f'{interaction.user.mention} забанил игрока')
        await interaction.response.edit_message(view=view, embed=embed)
    
    @discord.ui.button(label='Отмена', style=discord.ButtonStyle.primary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = createEmbedFromSteam(self.summary, 'Бан игрока отменен')
        await interaction.response.edit_message(content=None, view=None, embed=embed)


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
        try:
            summary = await Steam.GetPlayerSummaries(steam_id)
        except Exception as e:
            logger.info(f'Ban: player not found. {e}')
            await interaction.response.send_message('Игрок не найден', ephemeral=True)
            return
        embed = createEmbedFromSteam(summary, 'Подтвердите бан игрока',
                                     f'Steam ID: {steam_id}\nПричина: {reason}\nДлительность (секунды): {duration}')
        view = AcceptBanView(summary=summary, duration=duration, reason=reason)
        await interaction.response.send_message(embed=embed, ephemeral=True, view=view)
        
    
async def setup(bot: commands.Bot):
    await bot.add_cog(SourcebansCommands(bot), guild=discord.Object(id = settings.GUILD_ID))