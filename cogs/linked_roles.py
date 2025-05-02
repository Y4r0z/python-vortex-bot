import discord
import settings
from discord import app_commands
from discord.ext import commands
from tools.ds import checkAdmin
from ui.linked_roles import LinkedRolesView

logger = settings.logging.getLogger('discord')

class LinkedRolesCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()
        
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Обработчик события обновления участника (в том числе удаления ролей)"""
        try:
            if 'linked_roles' not in settings.Preferences:
                return
                
            removed_roles = set(before.roles) - set(after.roles)
            
            for role in removed_roles:
                role_id = str(role.id)
                if role_id in settings.Preferences['linked_roles']:
                    linked_role_id = settings.Preferences['linked_roles'][role_id]
                    linked_role = after.guild.get_role(linked_role_id)
                    if linked_role and linked_role in after.roles:
                        await after.remove_roles(linked_role)
                        logger.info(
                            f'Removed linked role {linked_role.id} from user {after.id} '
                            f'after primary role {role.id} was removed'
                        )
                        
        except Exception as e:
            logger.error(f'Error in on_member_update: {str(e)}')

    @app_commands.command(
        name='linkroles',
        description='Настройка автоматической выдачи связанных ролей'
    )
    @commands.has_permissions(administrator=True)
    async def linkroles(
        self,
        interaction: discord.Interaction
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(
            f'Link roles command called by {interaction.user.id} '
            f'({interaction.user.name})'
        )

        try:
            if not (await checkAdmin(interaction)):
                return

            view = LinkedRolesView()
            
            await interaction.followup.send(
                'Выберите роли для связывания:',
                view=view,
                ephemeral=True
            )
            logger.info('Linked roles setup menu sent')

        except Exception as e:
            logger.error(f'Error in link roles command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при настройке связанных ролей. '
                'Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

    @app_commands.command(
        name='unlink_roles',
        description='Удаляет связь между ролями'
    )
    @commands.has_permissions(administrator=True)
    async def unlink_roles(
        self,
        interaction: discord.Interaction,
        primary_role: discord.Role
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(
            f'Unlink roles command called by {interaction.user.id} '
            f'({interaction.user.name})'
        )

        try:
            if not (await checkAdmin(interaction)):
                return

            if 'linked_roles' not in settings.Preferences:
                settings.Preferences['linked_roles'] = {}

            role_id = str(primary_role.id)
            if role_id in settings.Preferences['linked_roles']:
                del settings.Preferences['linked_roles'][role_id]
                settings.SavePreferences()
                await interaction.followup.send(
                    f'Связь для роли {primary_role.mention} успешно удалена!',
                    ephemeral=True
                )
                logger.info(f'Role unlinked: {primary_role.id}')
            else:
                await interaction.followup.send(
                    f'Роль {primary_role.mention} не имеет связанных ролей',
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f'Error in unlink roles command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при удалении связи ролей. '
                'Пожалуйста, попробуйте позже.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(
        LinkedRolesCommand(bot),
        guild=discord.Object(id=settings.GUILD_ID)
    )
