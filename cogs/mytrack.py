import discord
import json
from typing import Optional
from discord import app_commands
from discord.ext import commands
from ytmusicapi import YTMusic

import settings
from tools.ds import tryGetOtherUser
from tools.music import TrackUtils, track_manager, music_converter
from ui.music import TrackSearchModal, create_navigation_view

logger = settings.logging.getLogger("discord")
EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)


def check_roles():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
            
        role_ids = load_role_ids()
        allowed_roles = {
            role_ids.get('moder_role_id'),
            role_ids.get('legend_role_id')
        }
        
        allowed_roles = {role_id for role_id in allowed_roles if role_id is not None}
        
        user_roles = {role.id for role in interaction.user.roles}
        if any(role_id in user_roles for role_id in allowed_roles):
            return True
            
        await interaction.response.send_message(
            "У вас недостаточно прав для использования этой команды.",
            ephemeral=True
        )
        return False
        
    return app_commands.check(predicate)


def load_role_ids():
    try:
        with open('preferences/ids.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f'Error loading role IDs: {str(e)}')
        return {}


class MyTrackCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()
        
        if hasattr(self.bot, 'music_initialized'):
            return
            
        music_converter.start_processing(self.bot.loop)
        self.bot.music_initialized = True

    def cog_unload(self):
        music_converter.stop_processing()

    @app_commands.command(
        name='mytrack',
        description='🎵 Установить любимый трек (поддерживает ссылки из разных сервисов)'
    )
    @check_roles()
    async def mytrack(self, interaction: discord.Interaction) -> None:
        logger.info(f'MyTrack command called by {interaction.user.id} ({interaction.user.name})')
        try:
            vortex_user = await tryGetOtherUser(interaction.user, interaction)
            if not vortex_user:
                await interaction.response.send_message(
                    "Для использования этой команды необходимо связать свой Steam аккаунт. Используйте команду /link",
                    ephemeral=True
                )
                return
                
            steam_id = vortex_user['steamId']
            try:
                current_track = await track_manager.get_current_track(steam_id)
                await self.show_current_track(interaction, steam_id)
            except Exception as api_error:
                logger.warning(f'API error while getting current track for {steam_id}: {str(api_error)}')
                await self.show_next_season_track(interaction, steam_id)
                
        except Exception as e:
            logger.error(f'Unexpected error in mytrack command: {str(e)}')
            embed = TrackUtils.create_track_embed(
                title="❌ Ошибка",
                track_name="Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    
    
    async def show_current_track(self, interaction: discord.Interaction, steam_id: str) -> None:
        try:
            current_track = await track_manager.get_current_track(steam_id)
            if not current_track:
                await self.show_next_season_track(interaction, steam_id)
                return

            thumbnail_url = await TrackUtils.get_youtube_thumbnail(current_track.get('url', ''))

            platform_links = TrackUtils.get_platform_links(current_track['soundname'])
            
            embed = discord.Embed(color=EMBED_COLOR)
            embed.description = (
                f"🎵 **Ваш текущий трек**\n"
                f"### {current_track['soundname']}\n"
                f"Прослушиваний: **{current_track.get('playcount', 0):,}**\n\n"
                f"{' • '.join(platform_links)}"
            )
            
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            view = create_navigation_view([
                ("Трек следующего сезона", "⏭️", discord.ButtonStyle.secondary, 
                 lambda i: self.show_next_season_track(i, steam_id)),
                ("Поделиться", "📢", discord.ButtonStyle.success,
                 lambda i: self.share_track(i, embed, current_track))
            ])

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.warning(f'Error showing current track for {steam_id}: {str(e)}')
            await self.show_next_season_track(interaction, steam_id)

    async def show_next_season_track(self, interaction: discord.Interaction, steam_id: str) -> None:
        next_track = await track_manager.get_next_season_track(steam_id)
        
        if not next_track:
            can_set = await track_manager.can_set_track()
            if can_set:
                await self.show_no_track_message(interaction, is_next_season=True)
            else:
                embed = discord.Embed(color=EMBED_COLOR)
                embed.description = (
                    "⏭️ **Трек следующего сезона**\n"
                    "### Установка трека на следующий сезон доступна с 20 по 30 число каждого месяца."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        thumbnail_url = await TrackUtils.get_youtube_thumbnail(next_track.get('url', ''))
        
        platform_links = TrackUtils.get_platform_links(next_track['soundname'])
        
        embed = discord.Embed(color=EMBED_COLOR)
        embed.description = (
            f"⏭️ **Ваш трек на следующий сезон**\n"
            f"### {next_track['soundname']}\n\n"
            f"{' • '.join(platform_links)}"
        )
        
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
            
        embed.set_footer(text="Вы можете изменить трек, нажав кнопку ниже")
        
        view = create_navigation_view([
            ("Изменить трек", "🔄", discord.ButtonStyle.primary, 
             lambda i: self._show_track_search_modal(i)),
            ("Текущий трек", "◀️", discord.ButtonStyle.secondary,
             lambda i: self.show_current_track(i, steam_id)),
        ])

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _show_track_search_modal(self, interaction: discord.Interaction) -> None:
        modal = TrackSearchModal(self.bot)
        await interaction.response.send_modal(modal)

    async def show_no_track_message(self, interaction: discord.Interaction, is_next_season: bool = False) -> None:
        title = "⏭️ Трек следующего сезона" if is_next_season else "🎵 Любимый трек"
        
        embed = discord.Embed(color=EMBED_COLOR)
        embed.description = (
            f"**{title}**\n"
            f"### У вас пока нет установленного трека. Нажмите кнопку ниже, чтобы добавить его!"
        )
        
        view = create_navigation_view([
            ("Искать трек", "🔍", discord.ButtonStyle.primary, 
             lambda i: self._show_track_search_modal(i))
        ])
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def share_track(
        self, 
        interaction: discord.Interaction, 
        source_embed: discord.Embed,
        track_data: dict
    ) -> None:
        platform_links = TrackUtils.get_platform_links(track_data['soundname'])
        
        public_embed = discord.Embed(color=EMBED_COLOR)
        public_embed.description = (
            f"🎵 **Трек игрока** {interaction.user.mention}\n"
            f"### {track_data['soundname']}\n"
            f"Прослушиваний: **{track_data.get('playcount', 0)}**\n\n"
            f"{' • '.join(platform_links)}"
        )
        
        if source_embed.thumbnail:
            public_embed.set_thumbnail(url=source_embed.thumbnail.url)
        
        await interaction.response.send_message(embed=public_embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(
        MyTrackCommand(bot),
        guild=discord.Object(id=settings.GUILD_ID)
    )