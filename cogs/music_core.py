import json
import asyncio
from typing import Dict, Any
import discord
from discord import app_commands
from discord.ext import commands
import settings

import lib.vortex_api as Vortex
from tools.ds import checkAdmin

logger = settings.logging.getLogger('discord')

class MusicCore(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @app_commands.command(
        name="pushtracks",
        description="Загружает треки из локального файла в API и отображает топ треков"
    )
    async def push_tracks(self, interaction: discord.Interaction):
        logger.info(f'Pushtracks command called by {interaction.user.id} ({interaction.user.name})')
        
        if not await checkAdmin(interaction):
            logger.warning(f'Access denied for {interaction.user.id} ({interaction.user.name})')
            return
            
        try:
            await interaction.response.send_message("Начинаю загрузку треков...")
            
            try:
                with open("preferences/ids.json", "r", encoding="utf-8") as f:
                    ids_data = json.load(f)
                    legend_role_id = ids_data["legend_role_id"]
                    moder_role_id = ids_data["moder_role_id"]
                    logger.info(f'Successfully loaded ids.json with legend_role_id={legend_role_id}, moder_role_id={moder_role_id}')
            except Exception as e:
                logger.error(f'Error loading ids.json: {str(e)}')
                await interaction.edit_original_response(
                    content="❌ Ошибка при загрузке ids.json!"
                )
                return
            
            try:
                with open("preferences/tracks.json", "r", encoding="utf-8") as f:
                    tracks_data: Dict[str, Any] = json.load(f)
                    logger.info(f'Successfully loaded tracks.json with {len(tracks_data)} entries')
            except FileNotFoundError:
                logger.error('tracks.json file not found')
                await interaction.edit_original_response(
                    content="❌ Файл tracks.json не найден!"
                )
                return
            except json.JSONDecodeError:
                logger.error('Error parsing tracks.json')
                await interaction.edit_original_response(
                    content="❌ Ошибка чтения JSON файла!"
                )
                return
                
            success_count = 0
            skipped_count = 0
            error_count = 0
            
            await interaction.edit_original_response(
                content=f"Начинаю загрузку {len(tracks_data)} треков..."
            )
            
            for steam_id, track_info in tracks_data.items():
                try:
                    privilege_set = await Vortex.GetPrivilegeSet(steam_id)
                    
                    if not (privilege_set["legend"] or privilege_set["moderator"]):
                        skipped_count += 1
                        logger.info(f'Skipped uploading track for {steam_id} - no Legend or Moderator status')
                        continue
                    
                    track_data = {
                        "soundname": track_info.get("soundname", ""),
                        "path": track_info.get("path", ""),
                        "url": track_info.get("url")
                    }
                    
                    logger.debug(f'Uploading track for {steam_id}: {track_data["soundname"]}')
                    await Vortex.UpdatePlayerTrack(steam_id, track_data)
                    success_count += 1
                    logger.info(f'Successfully uploaded track for {steam_id}')
                    
                    if (success_count + skipped_count + error_count) % 10 == 0:
                        status_msg = f"Загружено {success_count}/{len(tracks_data)} треков, пропущено {skipped_count}..."
                        logger.info(status_msg)
                        await interaction.edit_original_response(content=status_msg)
                        
                except Exception as e:
                    error_msg = f"Ошибка при загрузке трека для {steam_id}: {str(e)}"
                    logger.error(error_msg)
                    error_count += 1
                    
                await asyncio.sleep(0.5)
            
            status_message = f"""Загрузка завершена!
✅ Успешно загружено: {success_count}
⏭️ Пропущено (нет привилегий): {skipped_count}
❌ Ошибок: {error_count}
📊 Всего треков: {len(tracks_data)}

Получаю топ-10 треков по прослушиваниям..."""
            
            await interaction.edit_original_response(content=status_message)
            
            top_tracks = await Vortex.GetTopTracks(10)
            
            embed = discord.Embed(
                title="🎵 Топ-10 треков по прослушиваниям",
                color=discord.Color.from_rgb(88, 101, 242)
            )
            
            for i, track in enumerate(top_tracks):
                steam_id = track["user"]["steamId"]
                track_name = track["soundname"]
                playcount = track["playcount"]
                
                discord_user = None
                try:
                    discord_link = await Vortex.GetDiscordUserSteam(steam_id)
                    if discord_link:
                        discord_id = discord_link["discordId"]
                        discord_user = self.bot.get_user(int(discord_id)) or await self.bot.fetch_user(int(discord_id))
                except Exception as e:
                    logger.warning(f"Could not find Discord user for Steam ID {steam_id}: {str(e)}")
                
                if discord_user:
                    user_mention = f"{discord_user.mention} ({discord_user.name})"
                else:
                    user_mention = f"Игрок (Steam ID: {steam_id})"
                
                medal = ""
                if i == 0:
                    medal = "🥇 "
                elif i == 1:
                    medal = "🥈 "
                elif i == 2:
                    medal = "🥉 "
                else:
                    medal = f"{i+1}. "
                
                embed.add_field(
                    name=f"{medal}{track_name}",
                    value=f"**Игрок:** {user_mention}\n**Прослушиваний:** {playcount:,}",
                    inline=False
                )
            
            embed.set_footer(text="Последнее обновление: " + discord.utils.utcnow().strftime("%d.%m.%Y %H:%M UTC"))
            
            await interaction.edit_original_response(content=None, embed=embed)
            logger.info(f'Top tracks displayed successfully')
            
        except Exception as e:
            error_msg = f"Общая ошибка в команде pushtracks: {str(e)}"
            logger.error(error_msg)
            await interaction.edit_original_response(
                content=f"❌ Произошла ошибка при выполнении команды: {str(e)}"
            )

    @app_commands.command(
        name="synctracks",
        description="Синхронизирует треки с привилегиями пользователей"
    )
    async def sync_tracks(self, interaction: discord.Interaction):
        logger.info(f'Synctracks command called by {interaction.user.id} ({interaction.user.name})')
        
        if not await checkAdmin(interaction):
            logger.warning(f'Access denied for {interaction.user.id} ({interaction.user.name})')
            return
            
        try:
            await interaction.response.send_message("Начинаю синхронизацию треков...")
            
            try:
                with open("preferences/ids.json", "r", encoding="utf-8") as f:
                    ids_data = json.load(f)
                    legend_role_id = ids_data["legend_role_id"]
                    moder_role_id = ids_data["moder_role_id"]
                    logger.info(f'Successfully loaded ids.json with legend_role_id={legend_role_id}, moder_role_id={moder_role_id}')
            except Exception as e:
                logger.error(f'Error loading ids.json: {str(e)}')
                await interaction.edit_original_response(
                    content="❌ Ошибка при загрузке ids.json!"
                )
                return
            
            try:
                with open("preferences/tracks.json", "r", encoding="utf-8") as f:
                    tracks_data: Dict[str, Any] = json.load(f)
                    logger.info(f'Successfully loaded tracks.json with {len(tracks_data)} entries')
            except FileNotFoundError:
                logger.error('tracks.json file not found')
                await interaction.edit_original_response(
                    content="❌ Файл tracks.json не найден!"
                )
                return
            except json.JSONDecodeError:
                logger.error('Error parsing tracks.json')
                await interaction.edit_original_response(
                    content="❌ Ошибка чтения JSON файла!"
                )
                return
                
            total_tracks = len(tracks_data)
            removed_tracks = 0
            errors = 0
            processed = 0
            
            await interaction.edit_original_response(
                content=f"Проверяю {total_tracks} треков на соответствие привилегиям..."
            )
            
            for steam_id, track_info in tracks_data.items():
                processed += 1
                try:
                    privilege_set = await Vortex.GetPrivilegeSet(steam_id)
                    
                    if not (privilege_set["legend"] or privilege_set["moderator"]):
                        await Vortex.DeletePlayerTrack(steam_id)
                        removed_tracks += 1
                        logger.info(f'Removed track from API for {steam_id} - no Legend or Moderator status')
                        
                except Exception as e:
                    error_msg = f"Ошибка при проверке трека для {steam_id}: {str(e)}"
                    logger.error(error_msg)
                    errors += 1
                
                if processed % 10 == 0:
                    status_msg = f"Проверено {processed}/{total_tracks} треков. Удалено из API {removed_tracks}..."
                    await interaction.edit_original_response(content=status_msg)
                    
                await asyncio.sleep(0.5)
            
            final_message = f"""Синхронизация треков завершена!
✅ Проверено треков: {total_tracks}
🔴 Удалено треков из API: {removed_tracks}
❌ Ошибок: {errors}"""
            
            logger.info(f'Tracks sync completed. Total: {total_tracks}, Removed from API: {removed_tracks}, Errors: {errors}')
            await interaction.edit_original_response(content=final_message)
            
        except Exception as e:
            error_msg = f"Общая ошибка в команде synctracks: {str(e)}"
            logger.error(error_msg)
            await interaction.edit_original_response(
                content=f"❌ Произошла ошибка при выполнении команды: {str(e)}"
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(
        MusicCore(bot),
        guild=discord.Object(id=settings.GUILD_ID)
    )