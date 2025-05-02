import discord
import settings
from discord.ext import commands

logger = settings.logging.getLogger('discord')

class WelcomeEvents(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        try:
            welcome_channel_id = settings.Get('bot_welcome_channel_id', None)
            if not welcome_channel_id:
                logger.warning('Welcome channel not set up')
                return

            channel = self.bot.get_channel(welcome_channel_id)
            if not channel:
                logger.error(f'Could not find welcome channel with ID {welcome_channel_id}')
                return

            welcome_message = (
                f"Привет, {member.mention} 👋\n\n"
                "Для доступа ко всем функциям сервера, введите команду `/link`\n"
                "и следуйте инструкциям для привязки вашего Steam аккаунта."
            )

            await channel.send(welcome_message)
            logger.info(f'Sent welcome message to {member.id} ({member.name})')

        except Exception as e:
            logger.error(f'Error in welcome event: {str(e)}')

async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeEvents(bot), guild=discord.Object(id=settings.GUILD_ID))