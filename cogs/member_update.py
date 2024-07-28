import discord
import settings
from discord.ext import commands
from tools.ds import checkAdmin, syncAllRoles
import lib.vortex_api as Vortex

logger = settings.logging.getLogger('discord')


class MemberUpdateEvent(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        
        super().__init__()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        logger.info(f'Member update event for {before.id} ({before.name}))')
        if not settings.IsSetUp():
            logger.error('Bot is not set up: return')
            return
        if len(before.roles) == len(after.roles):
            logger.info('No changes in roles detected: return')
            return
        await syncAllRoles(after)


async def setup(bot: commands.Bot):
    await bot.add_cog(MemberUpdateEvent(bot), guild=discord.Object(id = settings.GUILD_ID))