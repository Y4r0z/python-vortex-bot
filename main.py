import discord.ext
import discord.ext.commands
import settings
import discord
from discord.ext import commands
from ui.steam_link import LinkView
import lib.vortex_api as Vortex
from ui.setup import SetupView
from ui.balance import SendWallet, PayWarnView, BalanceShareView
from tools.text import formatCoins
import pathlib
from tools.discord import checkAdmin, tryGetUser

logger = settings.logging.getLogger('discord')
    

async def reloadBotCommands(bot: commands.Bot):
    for cog in settings.COGS_DIR.glob("*.py"):
            if cog == "__init__.py": continue
            try:
                 await bot.load_extension(f'cogs.{cog.name[:-3]}')
            except discord.ext.commands.errors.ExtensionAlreadyLoaded:
                 await bot.reload_extension(f'cogs.{cog.name[:-3]}')

def main():
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    guild = discord.Object(id=settings.GUILD_ID)

    bot = commands.Bot(intents=intents, command_prefix='!')    

    @bot.event
    async def on_ready():
        logger.info('Bot started')
        await reloadBotCommands(bot)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        logger.info('Guild initialized')
        
    @bot.tree.command(name='reloadcommands', description='Перезагружает все команды из файлов')
    @commands.has_permissions(administrator=True)
    async def reloadCommands(interaction: discord.Interaction):
        if not (await checkAdmin(interaction)): return
        logger.info(f'Пользователь {interaction.user.id} перезагружает команды')
        await reloadBotCommands(bot)
        await interaction.response.send_message('Команды перезагружены!', ephemeral=True)

    bot.run(settings.DISCORD_TOKEN, root_logger=True)


if __name__ == '__main__':
    main()