import discord
import settings
from discord.ext import commands
from discord import app_commands
from tools.ds import checkAdmin, syncAllRoles, tryGetUser
import lib.vortex_api as Vortex
from typing import Optional

logger = settings.logging.getLogger('discord')


class SyncCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot   
        super().__init__()

    @app_commands.command(name='sync', description='Синхронизирует ваши привелегии Discord с привелегиями на серверах Vortex')
    async def sync_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Sync command called by: {interaction.user.id} ({interaction.user.name})')
        
        try:
            if (await tryGetUser(interaction)) is None:
                return
            
            member = interaction.user
            if not isinstance(member, discord.Member):
                await interaction.followup.send('Вы выполнили команду не на сервере!', ephemeral=True)
                return

            await syncAllRoles(member)
            
            try:
                if (role := settings.Preferences['linked_role_id']) not in [i.id for i in member.roles]:
                    await member.add_roles(discord.Object(id=role))
            except Exception as e:
                logger.error(f'Error adding linked role: {str(e)}')
                
            await interaction.followup.send('Синхронизация проведена успешно.', ephemeral=True)
            logger.info('Sync: Ok')
            
        except Exception as e:
            logger.error(f'Error in sync command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при синхронизации. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )
    
    @app_commands.command(name='syncuser', description='Синхронизирует определенного пользователя')
    async def syncuser(self, interaction: discord.Interaction, member: discord.Member) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'SyncUser command called by: {interaction.user.id} ({interaction.user.name})')
        
        try:
            if not await checkAdmin(interaction):
                await interaction.followup.send('У вас недостаточно прав для выполнения этой команды.', ephemeral=True)
                return

            await syncAllRoles(member)
            
            try:
                if (role := settings.Preferences['linked_role_id']) not in [i.id for i in member.roles]:
                    await member.add_roles(discord.Object(id=role))
            except Exception as e:
                logger.error(f'Error adding linked role: {str(e)}')
            
            await interaction.followup.send(f'Синхронизация пользователя {member.mention} проведена успешно.', ephemeral=True)
            logger.info('SyncUser: Ok')
            
        except Exception as e:
            logger.error(f'Error in syncuser command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при синхронизации пользователя. Пожалуйста, попробуйте позже.',
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCommand(bot), guild=discord.Object(id=settings.GUILD_ID))