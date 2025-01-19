import json
import discord
import settings
from discord import app_commands
from discord.ext import commands
import asyncio
from typing import Dict, Any
import lib.vortex_api as Vortex
from tools.ds import checkAdmin

logger = settings.logging.getLogger('discord')

class MusicCore(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @app_commands.command(
        name="pushtracks",
        description="Загружает треки из локального файла в API"
    )
    async def push_tracks(self, interaction: discord.Interaction):
        logger.info(f'Pushtracks command called by {interaction.user.id} ({interaction.user.name})')
        
        if not await checkAdmin(interaction):
            logger.warning(f'Access denied for {interaction.user.id} ({interaction.user.name})')
            return
            
        try:
            await interaction.response.send_message("Начинаю загрузку треков...")
            
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
            error_count = 0
            
            await interaction.edit_original_response(
                content=f"Начинаю загрузку {len(tracks_data)} треков..."
            )
            
            for steam_id, track_info in tracks_data.items():
                try:
                    track_data = {
                        "soundname": track_info.get("soundname", ""),
                        "path": track_info.get("path", ""),
                        "url": track_info.get("url")
                    }
                    
                    logger.debug(f'Uploading track for {steam_id}: {track_data["soundname"]}')
                    await Vortex.UpdatePlayerTrack(steam_id, track_data)
                    success_count += 1
                    logger.info(f'Successfully uploaded track for {steam_id}')
                    
                    if success_count % 10 == 0:
                        status_msg = f"Загружено {success_count}/{len(tracks_data)} треков..."
                        logger.info(status_msg)
                        await interaction.edit_original_response(content=status_msg)
                        
                except Exception as e:
                    error_msg = f"Ошибка при загрузке трека для {steam_id}: {str(e)}"
                    logger.error(error_msg)
                    error_count += 1
                    
                await asyncio.sleep(0.5)
            
            final_message = f"""Загрузка завершена!
✅ Успешно загружено: {success_count}
❌ Ошибок: {error_count}
📊 Всего треков: {len(tracks_data)}"""
            
            logger.info(f'Upload completed. Success: {success_count}, Errors: {error_count}, Total: {len(tracks_data)}')
            await interaction.edit_original_response(content=final_message)
            
        except Exception as e:
            error_msg = f"Общая ошибка в команде pushtracks: {str(e)}"
            logger.error(error_msg)
            await interaction.edit_original_response(
                content=f"❌ Произошла ошибка при выполнении команды: {str(e)}"
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(
        MusicCore(bot),
        guild=discord.Object(id=settings.GUILD_ID)
    )