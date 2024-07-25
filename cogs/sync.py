import discord
import settings
from discord.ext import commands
from discord import app_commands
from tools.ds import checkAdmin, syncAllRoles, tryGetUser
import lib.vortex_api as Vortex

logger = settings.logging.getLogger('discord')


class SyncCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot   
        super().__init__()

    @app_commands.command(name='sync', description='Синхронизирует ваши привелегии Discord с привелегиями на серверах Vortex')
    async def sync_command(self, interaction: discord.Interaction):
        logger.info(f'Sync command called by: {interaction.user.id} ({interaction.user.name}))')
        if (await tryGetUser(interaction)) is None: return
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message('Вы выполнили команду не на сервере!', ephemeral=True)
            return
        await syncAllRoles(member)
        await interaction.response.send_message('Синхронизация проведена.', ephemeral=True)
        if (role:=settings.Preferences['linked_role_id']) not in [i.id for i in member.roles]:
            await member.add_roles(discord.Object(id=role))
        logger.info('Sync: Ok')


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCommand(bot), guild=discord.Object(id = settings.GUILD_ID))