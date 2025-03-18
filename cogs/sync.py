import discord
import settings
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
from tools.ds import checkAdmin, syncAllRoles, tryGetUser
import lib.vortex_api as Vortex
from typing import Dict, Optional

# Используем специальный логгер для синхронизации
logger = settings.logging.getLogger('discord.sync')


class SyncCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot   
        self.privilege_sync_task.start()
        super().__init__()
    
    def cog_unload(self):
        self.privilege_sync_task.cancel()
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Обработчик события присоединения нового участника к серверу"""
        logger.info(f"New member joined: {member.id} ({member.name})")
        
        try:
            # Проверяем, привязан ли аккаунт Discord к Steam
            try:
                discord_user = await Vortex.GetDiscordUser(member.id)
                if discord_user:
                    steam_id = discord_user["user"]["steamId"]
                    
                    # Выдаем роль привязанного аккаунта
                    if 'linked_role_id' in settings.Preferences:
                        linked_role_id = settings.Preferences['linked_role_id']
                        await member.add_roles(discord.Object(id=linked_role_id))
                        logger.info(f"Added linked role to new member {member.id} ({member.name})")
                    
                    # Синхронизируем привилегии
                    await self.sync_member_privileges(member, steam_id)
                    logger.info(f"Synchronized privileges for new member {member.id} ({member.name})")
            except Exception as e:
                logger.debug(f"New member {member.id} not linked: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error syncing privileges for new member {member.id} ({member.name}): {str(e)}")
        
    @tasks.loop(hours=12)
    async def privilege_sync_task(self):
        try:
            logger.info("Starting scheduled privilege sync for all users")
            await self.sync_all_users_privileges()
            logger.info("Completed scheduled privilege sync for all users")
        except Exception as e:
            logger.error(f"Error in scheduled privilege sync: {str(e)}")
    
    @privilege_sync_task.before_loop
    async def before_privilege_sync(self):
        await self.bot.wait_until_ready()

    async def sync_member_privileges(self, member: discord.Member, steam_id: str) -> int:
        try:
            privilege_set = await Vortex.GetPrivilegeSet(steam_id)
            member_role_ids = [role.id for role in member.roles]
            changes_made = 0
            
            # Проверяем наличие роли привязанного аккаунта
            if 'linked_role_id' in settings.Preferences:
                linked_role_id = settings.Preferences['linked_role_id']
                if linked_role_id not in member_role_ids:
                    await member.add_roles(discord.Object(id=linked_role_id))
                    logger.info(f"Added linked role to {member.id} ({member.name})")
                    changes_made += 1
            
            if 'vip_role_id' in settings.Preferences:
                vip_role_id = settings.Preferences['vip_role_id']
                if privilege_set["vip"] and vip_role_id not in member_role_ids:
                    await member.add_roles(discord.Object(id=vip_role_id))
                    logger.info(f"Added VIP role to {member.id} ({member.name})")
                    changes_made += 1
                elif not privilege_set["vip"] and vip_role_id in member_role_ids:
                    await member.remove_roles(discord.Object(id=vip_role_id))
                    logger.info(f"Removed VIP role from {member.id} ({member.name})")
                    changes_made += 1
            
            if 'premium_role_id' in settings.Preferences:
                premium_role_id = settings.Preferences['premium_role_id']
                if privilege_set["premium"] and premium_role_id not in member_role_ids:
                    await member.add_roles(discord.Object(id=premium_role_id))
                    logger.info(f"Added Premium role to {member.id} ({member.name})")
                    changes_made += 1
                elif not privilege_set["premium"] and premium_role_id in member_role_ids:
                    await member.remove_roles(discord.Object(id=premium_role_id))
                    logger.info(f"Removed Premium role from {member.id} ({member.name})")
                    changes_made += 1
            
            if 'legend_role_id' in settings.Preferences:
                legend_role_id = settings.Preferences['legend_role_id']
                if privilege_set["legend"] and legend_role_id not in member_role_ids:
                    await member.add_roles(discord.Object(id=legend_role_id))
                    logger.info(f"Added Legend role to {member.id} ({member.name})")
                    changes_made += 1
                elif not privilege_set["legend"] and legend_role_id in member_role_ids:
                    await member.remove_roles(discord.Object(id=legend_role_id))
                    logger.info(f"Removed Legend role from {member.id} ({member.name})")
                    changes_made += 1
            
            return changes_made
            
        except Exception as e:
            logger.error(f"Error checking privileges for user {member.id} ({member.name}): {str(e)}")
            return 0
    
    async def sync_all_users_privileges(self):
        if not settings.IsSetUp():
            logger.warning("Bot is not fully set up, skipping privilege sync")
            return
            
        guild = self.bot.get_guild(int(settings.GUILD_ID))
        if not guild:
            logger.error(f"Could not find guild with ID {settings.GUILD_ID}")
            return
            
        sync_count = 0
        error_count = 0
        
        batch_size = 20
        member_list = list(guild.members)
        
        for i in range(0, len(member_list), batch_size):
            batch = member_list[i:i+batch_size]
            
            for member in batch:
                if member.bot:
                    continue
                    
                try:
                    try:
                        discord_user = await Vortex.GetDiscordUser(member.id)
                        if not discord_user:
                            continue
                            
                        steam_id = discord_user["user"]["steamId"]
                        
                        # Проверяем наличие роли привязанного аккаунта
                        linked_role_id = settings.Preferences.get('linked_role_id')
                        if linked_role_id and linked_role_id not in [role.id for role in member.roles]:
                            # Если привязка существует, но роли нет - добавляем роль
                            await member.add_roles(discord.Object(id=linked_role_id))
                            logger.info(f"Added linked role to {member.id} ({member.name}) - Steam linked but role missing")
                            sync_count += 1
                        
                        # Двусторонняя синхронизация
                        changes1 = await self.sync_member_privileges(member, steam_id)
                        await syncAllRoles(member)
                        
                        if changes1 > 0:
                            sync_count += 1
                            
                    except Exception as e:
                        logger.debug(f"User {member.id} not linked: {str(e)}")
                        continue
                        
                except Exception as e:
                    logger.error(f"Error syncing privileges for user {member.id} ({member.name}): {str(e)}")
                    error_count += 1
            
            await asyncio.sleep(2)
                
        logger.info(f"Privilege sync completed. Users modified: {sync_count}, Errors: {error_count}")

    @app_commands.command(name='sync', description='Синхронизирует ваши привелегии между Discord и серверами Vortex')
    async def sync_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'Sync command called by: {interaction.user.id} ({interaction.user.name})')
        
        try:
            user_data = await tryGetUser(interaction)
            if user_data is None:
                return
            
            member = interaction.user
            if not isinstance(member, discord.Member):
                await interaction.followup.send('Вы выполнили команду не на сервере!', ephemeral=True)
                return

            # Двусторонняя синхронизация
            steam_id = user_data["steamId"]
            
            # Привилегии сервера -> Discord роли
            await self.sync_member_privileges(member, steam_id)
            
            # Discord роли -> привилегии сервера
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

            # Проверяем, привязан ли пользователь
            try:
                discord_user = await Vortex.GetDiscordUser(member.id)
                if discord_user:
                    steam_id = discord_user["user"]["steamId"]
                    
                    # Двусторонняя синхронизация
                    await self.sync_member_privileges(member, steam_id)
                    await syncAllRoles(member)
            except Exception as e:
                logger.debug(f'User not linked: {str(e)}')
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
    
    @app_commands.command(
        name='syncall', 
        description='Синхронизирует привилегии всех пользователей Discord с их привилегиями на серверах Vortex'
    )
    @commands.has_permissions(administrator=True)
    async def syncall_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        logger.info(f'SyncAll command called by: {interaction.user.id} ({interaction.user.name})')
        
        try:
            if not await checkAdmin(interaction):
                return
                
            await interaction.followup.send(
                'Начата синхронизация привилегий всех пользователей. Это может занять некоторое время.',
                ephemeral=True
            )
            
            await self.sync_all_users_privileges()
            
            await interaction.followup.send(
                'Синхронизация привилегий всех пользователей завершена успешно.',
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f'Error in syncall command: {str(e)}')
            await interaction.followup.send(
                'Произошла ошибка при синхронизации привилегий. Пожалуйста, проверьте логи.',
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCommand(bot), guild=discord.Object(id=settings.GUILD_ID))