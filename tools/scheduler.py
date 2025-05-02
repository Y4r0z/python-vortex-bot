import asyncio
import datetime
from discord.ext import tasks
import settings

logger = settings.logging.getLogger('tasks')

class Scheduler:
    def __init__(self, bot):
        self.bot = bot
        self.sync_in_progress = False
        self.sync_lock = asyncio.Lock()
        
        self.sync_hour = settings.Get('sync_hour', 23, lambda x: int(x))
        self.sync_minute = settings.Get('sync_minute', 0, lambda x: int(x))
        
        logger.info(f"Scheduler initialized, sync time: {self.sync_hour}:{self.sync_minute:02d}")
        
    def start_tasks(self):
        """Запускает все запланированные задачи"""
        logger.info("Starting scheduled tasks")
        
        self.daily_sync.change_interval(
            time=datetime.time(hour=self.sync_hour, minute=self.sync_minute)
        )
        self.daily_sync.start()
        
    def stop_tasks(self):
        """Останавливает все запланированные задачи"""
        logger.info("Stopping scheduled tasks")
        if self.daily_sync.is_running():
            self.daily_sync.cancel()
            
    def is_sync_running(self):
        """Проверяет, выполняется ли сейчас синхронизация"""
        return self.sync_in_progress
    
    async def run_sync_now(self):
        """Принудительно запускает синхронизацию привилегий"""
        if self.sync_in_progress:
            logger.warning("Sync is already in progress, skipping manual run")
            return False
            
        logger.info("Manual sync requested, starting now")
        await self._run_sync()
        return True
    
    async def _run_sync(self):
        """Внутренний метод запуска синхронизации с блокировкой"""
        async with self.sync_lock:
            if self.sync_in_progress:
                logger.warning("Sync is already in progress, skipping")
                return
                
            self.sync_in_progress = True
            try:
                sync_command = self.bot.get_cog("SyncCommand")
                if sync_command:
                    await sync_command.sync_all_users_privileges()
                    logger.info("Privileges sync completed successfully")
                else:
                    logger.error("SyncCommand cog not found")
            except Exception as e:
                logger.error(f"Error in privileges sync: {str(e)}")
            finally:
                self.sync_in_progress = False
    
    async def set_sync_time(self, hour, minute):
        """Устанавливает новое время для ежедневной синхронизации"""
        if not (0 <= hour < 24 and 0 <= minute < 60):
            return False
            
        self.sync_hour = hour
        self.sync_minute = minute
        
        settings.Preferences['sync_hour'] = hour
        settings.Preferences['sync_minute'] = minute
        settings.SavePreferences()
        
        if self.daily_sync.is_running():
            self.daily_sync.cancel()
            
        self.daily_sync.change_interval(
            time=datetime.time(hour=hour, minute=minute)
        )
        self.daily_sync.start()
        
        logger.info(f"Sync time changed to {hour}:{minute:02d}")
        return True
    
    @tasks.loop(time=datetime.time(hour=23, minute=0))
    async def daily_sync(self):
        """Ежедневная синхронизация привилегий пользователей"""
        logger.info(f"Executing daily privileges sync at {datetime.datetime.now().strftime('%H:%M:%S')}")
        await self._run_sync()
            
    @daily_sync.before_loop
    async def before_daily_sync(self):
        """Ожидает готовности бота перед запуском задачи"""
        await self.bot.wait_until_ready()
        logger.info("Bot is ready, daily sync task is now waiting for scheduled time")