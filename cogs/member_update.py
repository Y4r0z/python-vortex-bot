import discord
import settings
from discord.ext import commands
from tools.ds import checkAdmin, syncAllRoles
import lib.vortex_api as Vortex
from typing import Optional

logger = settings.logging.getLogger('discord')

class MemberUpdateEvent(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        try:
            logger.info(f'Member update event for {before.id} ({before.name})')

            if not settings.IsSetUp():
                logger.error('Bot is not set up')
                return

            # Проверяем изменение ролей
            if len(before.roles) == len(after.roles):
                logger.info('No changes in roles detected')
                return

            # Логируем изменение ролей для отладки
            added_roles = set(after.roles) - set(before.roles)
            removed_roles = set(before.roles) - set(after.roles)
            
            if added_roles:
                logger.info(f'Added roles: {", ".join(role.name for role in added_roles)}')
            if removed_roles:
                logger.info(f'Removed roles: {", ".join(role.name for role in removed_roles)}')

            await syncAllRoles(after)
            logger.info(f'Roles synchronized successfully for user {after.id}')

        except Exception as e:
            logger.error(f'Error in member update event: {str(e)}')

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberUpdateEvent(bot), guild=discord.Object(id=settings.GUILD_ID))