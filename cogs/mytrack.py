import discord
import json
from discord import app_commands
from discord.ext import commands

import settings
from tools.ds import tryGetOtherUser
from tools.music import TrackUtils, track_manager, music_converter
from ui.music import TrackSearchModal, create_navigation_view

logger = settings.logging.getLogger("music")
EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)


def check_music_roles():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
            
        if TrackUtils.has_music_role(interaction.user):
            return True
            
        await interaction.response.send_message(
            "У вас недостаточно прав для использования этой команды.",
            ephemeral=True
        )
        return False
        
    return app_commands.check(predicate)


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
    @check_music_roles()
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
            await self.show_current_track(interaction, steam_id)
                
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
                await self.show_no_track_message(interaction)
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
            
            can_update = await track_manager.can_update_track(steam_id)
            view = None
            
            if can_update:
                view = create_navigation_view([
                    ("Изменить трек", "🔄", discord.ButtonStyle.primary, 
                     lambda i: self._show_track_search_modal(i)),
                    ("Поделиться", "📢", discord.ButtonStyle.success,
                     lambda i: self.share_track(i, embed, current_track))
                ])
            else:
                time_until_next = await track_manager.get_time_until_next_update(steam_id)
                if time_until_next:
                    embed.set_footer(text=f"Следующее обновление трека возможно через: {time_until_next}")
                
                view = create_navigation_view([
                    ("Трек можно будет изменить позже", "⏳", discord.ButtonStyle.secondary, 
                     lambda i: self.show_cooldown_message(i, time_until_next)),
                    ("Поделиться", "📢", discord.ButtonStyle.success,
                     lambda i: self.share_track(i, embed, current_track))
                ])

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f'Error showing current track for {steam_id}: {str(e)}')
            await self.show_no_track_message(interaction)

    async def show_cooldown_message(self, interaction: discord.Interaction, time_until_next: str) -> None:
        """Показывает сообщение о том, что трек пока нельзя обновить"""
        embed = discord.Embed(color=EMBED_COLOR)
        embed.description = (
            f"### ⏳ Период ожидания\n\n"
            f"Вы сможете обновить свой трек через **{time_until_next}**.\n\n"
            f"Обновление треков доступно раз в 14 дней."
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _show_track_search_modal(self, interaction: discord.Interaction) -> None:
        """Показывает модальное окно поиска трека"""
        try:
            vortex_user = await tryGetOtherUser(interaction.user, interaction)
            if not vortex_user:
                await interaction.response.send_message(
                    "Для использования этой команды необходимо связать свой Steam аккаунт. Используйте команду /link",
                    ephemeral=True
                )
                return
                
            steam_id = vortex_user['steamId']
            can_update = await track_manager.can_update_track(steam_id)
            
            if not can_update:
                time_until_next = await track_manager.get_time_until_next_update(steam_id)
                await self.show_cooldown_message(interaction, time_until_next)
                return
            
            modal = TrackSearchModal(self.bot)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f'Error showing track search modal: {str(e)}')
            await interaction.response.send_message(
                "Произошла ошибка при открытии поиска треков. Пожалуйста, попробуйте позже.",
                ephemeral=True
            )

    async def show_no_track_message(self, interaction: discord.Interaction) -> None:
        """Показывает сообщение об отсутствии трека"""
        embed = discord.Embed(color=EMBED_COLOR)
        embed.description = (
            f"**🎵 Любимый трек**\n"
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
        """Делится треком в канале"""
        platform_links = TrackUtils.get_platform_links(track_data['soundname'])
        
        public_embed = discord.Embed(color=EMBED_COLOR)
        public_embed.description = (
            f"🎵 **Трек игрока** {interaction.user.mention}\n"
            f"### {track_data['soundname']}\n"
            f"Прослушиваний: **{track_data.get('playcount', 0):,}**\n\n"
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