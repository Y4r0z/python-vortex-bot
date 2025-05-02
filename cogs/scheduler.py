import discord
from discord.ext import commands
import settings
from tools.scheduler import Scheduler
from discord import app_commands
from tools.ds import checkAdmin

logger = settings.logging.getLogger('tasks')

class SchedulerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.scheduler = Scheduler(bot)
        super().__init__()
        
    async def cog_load(self) -> None:
        """Вызывается при загрузке расширения"""
        logger.info("Initializing scheduler")
        self.scheduler.start_tasks()
        
    async def cog_unload(self) -> None:
        """Вызывается при выгрузке расширения"""
        logger.info("Stopping scheduler")
        self.scheduler.stop_tasks()
        
    @app_commands.command(
        name='sync_status',
        description='Показывает статус задачи синхронизации привилегий'
    )
    @commands.has_permissions(administrator=True)
    async def sync_status(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Sync status command called by: {interaction.user.id} ({interaction.user.name})')
        
        try:
            if not await checkAdmin(interaction):
                return
                
            is_running = self.scheduler.is_sync_running()
            next_run = self.scheduler.daily_sync.next_iteration
            
            status_message = "Статус синхронизации привилегий:\n"
            status_message += f"- Синхронизация запущена: {'Да' if is_running else 'Нет'}\n"
            status_message += f"- Время ежедневной синхронизации: {self.scheduler.sync_hour}:{self.scheduler.sync_minute:02d}\n"
            
            if next_run:
                status_message += f"- Следующий запуск: {next_run.strftime('%d.%m.%Y %H:%M:%S')}\n"
            else:
                status_message += "- Задача не запланирована\n"
                
            await interaction.followup.send(
                status_message,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f'Error in sync status command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при получении статуса синхронизации. Пожалуйста, проверьте логи.',
                ephemeral=True
            )
            
    @app_commands.command(
        name='run_sync',
        description='Запускает синхронизацию привилегий прямо сейчас'
    )
    @commands.has_permissions(administrator=True)
    async def run_sync(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Run sync command called by: {interaction.user.id} ({interaction.user.name})')
        
        try:
            if not await checkAdmin(interaction):
                return
                
            if self.scheduler.is_sync_running():
                await interaction.followup.send(
                    'Синхронизация уже выполняется. Пожалуйста, дождитесь её завершения.',
                    ephemeral=True
                )
                return
                
            await interaction.followup.send(
                'Запуск синхронизации привилегий...',
                ephemeral=True
            )
            
            success = await self.scheduler.run_sync_now()
            
            if success:
                await interaction.followup.send(
                    'Синхронизация привилегий выполнена успешно.',
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    'Не удалось запустить синхронизацию, так как она уже выполняется.',
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f'Error in run sync command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при запуске синхронизации. Пожалуйста, проверьте логи.',
                ephemeral=True
            )
            
    @app_commands.command(
        name='set_sync_time',
        description='Устанавливает время ежедневной синхронизации привилегий'
    )
    @commands.has_permissions(administrator=True)
    async def set_sync_time(
        self,
        interaction: discord.Interaction,
        hour: app_commands.Range[int, 0, 23],
        minute: app_commands.Range[int, 0, 59]
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Set sync time command called by: {interaction.user.id} ({interaction.user.name})')
        
        try:
            if not await checkAdmin(interaction):
                return
                
            success = await self.scheduler.set_sync_time(hour, minute)
            
            if success:
                await interaction.followup.send(
                    f'Время ежедневной синхронизации изменено на {hour}:{minute:02d}.',
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    'Не удалось изменить время синхронизации. Пожалуйста, проверьте введенные значения.',
                    ephemeral=True
                )
            
        except Exception as e:
            logger.error(f'Error in set sync time command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при изменении времени синхронизации. Пожалуйста, проверьте логи.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(
        SchedulerCog(bot),
        guild=discord.Object(id=settings.GUILD_ID)
    )