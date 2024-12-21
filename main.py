import discord.ext
import discord.ext.commands
import settings
import discord
from discord.ext import commands
from tools.ds import checkAdmin, tryGetUser #type: ignore

logger = settings.logging.getLogger('discord')
    

async def reloadBotCommands(bot: commands.Bot) -> None:
    """Перезагружает все команды бота из директории cogs"""
    logger.info("Начало перезагрузки команд")
    
    for cog in settings.COGS_DIR.glob("*.py"):
        if cog.name == "__init__.py":
            continue
            
        cog_name = f'cogs.{cog.name[:-3]}'
        try:
            try:
                await bot.unload_extension(cog_name)
            except discord.ext.commands.errors.ExtensionNotLoaded:
                pass
                
            await bot.load_extension(cog_name)
            logger.info(f"Успешно загружен модуль {cog_name}")
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке модуля {cog_name}: {str(e)}")
            continue
    
    logger.info("Завершение перезагрузки команд")

def main() -> None:
    """Основная функция запуска бота"""
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    guild = discord.Object(id=settings.GUILD_ID)

    bot = commands.Bot(intents=intents, command_prefix='!', heartbeat_timeout=60)    

    @bot.event
    async def on_ready() -> None:
        """Обработчик события готовности бота"""
        try:
            logger.info('Бот запущен')
            await reloadBotCommands(bot)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            logger.info('Сервер инициализирован')
        except Exception as e:
            logger.error(f'Ошибка при инициализации: {str(e)}')
        
    @bot.tree.command(name='reloadcommands', description='Перезагружает все команды из файлов')
    @commands.has_permissions(administrator=True)
    async def reloadCommands(interaction: discord.Interaction) -> None:
        """Команда для перезагрузки всех команд бота"""
        try:
            if not (await checkAdmin(interaction)):
                return
                
            logger.info(f'Пользователь {interaction.user.id} ({interaction.user.name}) перезагружает команды')
            await interaction.response.defer(ephemeral=True)
            
            await reloadBotCommands(bot)
            await interaction.followup.send('Команды успешно перезагружены!', ephemeral=True)
            
        except Exception as e:
            logger.error(f'Ошибка при перезагрузке команд: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при перезагрузке команд. Проверьте логи.',
                ephemeral=True
            )

    try:
        bot.run(settings.DISCORD_TOKEN, root_logger=True)
    except Exception as e:
        logger.error(f'Критическая ошибка при запуске бота: {str(e)}')


if __name__ == '__main__':
    main()
