import discord
import settings
from discord.ext import commands
from tools.ds import checkAdmin, syncAllRoles
import lib.vortex_api as Vortex
from typing import Optional, Set
from tools.music import TrackUtils, track_manager

logger = settings.logging.getLogger('discord.sync')

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

            if len(before.roles) == len(after.roles) and set(before.roles) == set(after.roles):
                return

            added_roles = set(after.roles) - set(before.roles)
            removed_roles = set(before.roles) - set(after.roles)
            
            before_role_ids = {role.id for role in before.roles}
            after_role_ids = {role.id for role in after.roles}
            
            vip_role_id = settings.Preferences.get('vip_role_id')
            premium_role_id = settings.Preferences.get('premium_role_id')
            legend_role_id = settings.Preferences.get('legend_role_id')
            
            key_roles_added = []
            key_roles_removed = []
            
            if vip_role_id:
                if vip_role_id in after_role_ids and vip_role_id not in before_role_ids:
                    key_roles_added.append(("VIP", vip_role_id))
                elif vip_role_id in before_role_ids and vip_role_id not in after_role_ids:
                    key_roles_removed.append(("VIP", vip_role_id))
                    
            if premium_role_id:
                if premium_role_id in after_role_ids and premium_role_id not in before_role_ids:
                    key_roles_added.append(("Premium", premium_role_id))
                elif premium_role_id in before_role_ids and premium_role_id not in after_role_ids:
                    key_roles_removed.append(("Premium", premium_role_id))
                    
            if legend_role_id:
                if legend_role_id in after_role_ids and legend_role_id not in before_role_ids:
                    key_roles_added.append(("Legend", legend_role_id))
                elif legend_role_id in before_role_ids and legend_role_id not in after_role_ids:
                    key_roles_removed.append(("Legend", legend_role_id))
            
            if key_roles_added:
                role_names = ", ".join([name for name, _ in key_roles_added])
                logger.info(f'Important roles added to {after.id} ({after.name}): {role_names}')
            
            if key_roles_removed:
                role_names = ", ".join([name for name, _ in key_roles_removed])
                logger.info(f'Important roles removed from {after.id} ({after.name}): {role_names}')

            try:
                discord_user = await Vortex.GetDiscordUser(after.id)
                if discord_user:
                    steam_id = discord_user["user"]["steamId"]
                    
                    had_music_role_before = TrackUtils.has_music_role(before)
                    has_music_role_after = TrackUtils.has_music_role(after)
                    
                    if had_music_role_before and not has_music_role_after:
                        logger.info(f'All music roles were removed from {after.id} ({after.name}), deleting track')
                        try:
                            await Vortex.DeletePlayerTrack(steam_id)
                            logger.info(f'Successfully deleted track for {after.id} ({after.name}) from API')
                        except Exception as track_error:
                            logger.error(f'Error deleting track for {after.id}: {str(track_error)}')
                    
                    if not had_music_role_before and has_music_role_after:
                        logger.info(f'Music role was added to {after.id} ({after.name}), checking track status')
                        await track_manager.compare_and_restore_track(steam_id)
                    
                    privileges_before = await Vortex.GetUserPrivileges(steam_id)
                    await syncAllRoles(after)
                    privileges_after = await Vortex.GetUserPrivileges(steam_id)
                    
                    privilege_changes = self._compare_privileges(privileges_before, privileges_after)
                    
                    if privilege_changes['added']:
                        logger.info(f'Privileges added for {after.id} ({after.name}): {", ".join(privilege_changes["added"])}')
                    
                    if privilege_changes['removed']:
                        logger.info(f'Privileges removed for {after.id} ({after.name}): {", ".join(privilege_changes["removed"])}')
                    
                    if not privilege_changes['added'] and not privilege_changes['removed'] and (key_roles_added or key_roles_removed):
                        logger.info(f'Roles changed for {after.id} ({after.name}) but no privilege changes detected')
                        
            except Exception as e:
                logger.debug(f'User {after.id} not linked or error: {str(e)}')
                if key_roles_added or key_roles_removed:
                    logger.info(f'Important role changes for {after.id} ({after.name}) but user not linked to Steam')
                await syncAllRoles(after)

        except Exception as e:
            logger.error(f'Error in member update event: {str(e)}')
    
    def _compare_privileges(self, before, after):
        result = {
            'added': [],
            'removed': []
        }
        
        before_types = {priv['privilege']['id']: priv['privilege']['name'] for priv in before}
        after_types = {priv['privilege']['id']: priv['privilege']['name'] for priv in after}
        
        for priv_id, name in after_types.items():
            if priv_id not in before_types:
                result['added'].append(name)
                
        for priv_id, name in before_types.items():
            if priv_id not in after_types:
                result['removed'].append(name)
                
        return result
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        try:
            logger.info(f'Member left server: {member.id} ({member.name})')
            
            if not settings.IsSetUp():
                logger.error('Bot is not set up')
                return
            
            vip_role_id = settings.Preferences.get('vip_role_id')
            premium_role_id = settings.Preferences.get('premium_role_id') 
            legend_role_id = settings.Preferences.get('legend_role_id')
            
            member_role_ids = {role.id for role in member.roles}
            important_roles = []
            
            if vip_role_id and vip_role_id in member_role_ids:
                important_roles.append("VIP")
                
            if premium_role_id and premium_role_id in member_role_ids:
                important_roles.append("Premium")
                
            if legend_role_id and legend_role_id in member_role_ids:
                important_roles.append("Legend")
            
            if important_roles:
                logger.info(f'User {member.id} ({member.name}) left server with roles: {", ".join(important_roles)}')
                
            try:
                discord_user = await Vortex.GetDiscordUser(member.id)
                if discord_user:
                    steam_id = discord_user["user"]["steamId"]
                    
                    privileges = await Vortex.GetUserPrivileges(steam_id)
                    removed_privileges = []
                    
                    for privilege in privileges:
                        if privilege['privilege']['id'] in [Vortex.PrivilegeTypeId.Vip, 
                                                           Vortex.PrivilegeTypeId.Premium, 
                                                           Vortex.PrivilegeTypeId.Legend]:
                            privilege_name = privilege['privilege']['name']
                            await Vortex.DeleteUserPrivilege(steam_id, privilege)
                            removed_privileges.append(privilege_name)
                            logger.info(f'Removed privilege {privilege_name} from {steam_id} ({member.name}) - user left server')
                    
                    if removed_privileges:
                        logger.info(f'Removed privileges for {member.id} ({member.name}) who left server: {", ".join(removed_privileges)}')
                    
                    if TrackUtils.has_music_role(member):
                        try:
                            await Vortex.DeletePlayerTrack(steam_id)
                            logger.info(f'Deleted track for user {member.id} ({member.name}) who left server with music role')
                        except Exception as track_error:
                            logger.error(f'Error deleting track for {member.id}: {str(track_error)}')
            except Exception as e:
                logger.debug(f'User {member.id} not linked or error: {str(e)}')
                
        except Exception as e:
            logger.error(f'Error in member remove event: {str(e)}')

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberUpdateEvent(bot), guild=discord.Object(id=settings.GUILD_ID))