import discord
from discord.ext import commands
from ytmusicapi import YTMusic
from typing import List, Dict, Any, Optional, Tuple, Callable

import settings
from tools.music import TrackUtils, get_track_info_from_url, music_converter, track_manager
from tools.ds import tryGetOtherUser

logger = settings.logging.getLogger('discord')
EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)


class TrackSelectView(discord.ui.View):
    def __init__(self, tracks: list, ytmusic: YTMusic, bot: commands.Bot, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.tracks = tracks
        self.ytmusic = ytmusic
        self.bot = bot
        self._add_track_buttons()

    def _truncate_text(self, text: str, max_length: int = 75) -> str:
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    def _add_track_buttons(self):
        for track in self.tracks[:5]:
            button_text = f"{track['title']} - {track['artists'][0]['name']}"
            truncated_text = self._truncate_text(button_text)
            
            button = discord.ui.Button(
                label=truncated_text,
                style=discord.ButtonStyle.secondary,
                custom_id=f"track_{track['videoId']}"
            )
            button.callback = self.track_button_callback
            self.add_item(button)

    async def track_button_callback(self, interaction: discord.Interaction):
        video_id = interaction.data['custom_id'].replace('track_', '')
        track = next(t for t in self.tracks if t['videoId'] == video_id)
        
        embed = TrackUtils.create_track_embed(
            title="🎧 Предпрослушивание",
            track_name=f"{track['title']}\n*{track['artists'][0]['name']}*",
            thumbnail_url=track['thumbnails'][0]['url']
        )
        
        preview_view = TrackPreviewView(track, self.tracks, self.ytmusic, self.bot)
        await interaction.response.edit_message(embed=embed, view=preview_view)


class TrackPreviewView(discord.ui.View):
    def __init__(self, track: dict, tracks: list, ytmusic: YTMusic, bot: commands.Bot):
        super().__init__()
        self.track = track
        self.tracks = tracks
        self.ytmusic = ytmusic
        self.bot = bot
        self._add_platform_buttons()
        self._add_navigation_buttons()
    
    def _add_platform_buttons(self):
        search_query = f"{self.track['title']} {self.track['artists'][0]['name']}"
        
        for platform in TrackUtils.MUSIC_PLATFORMS.values():
            url = (
                f"https://music.youtube.com/watch?v={self.track['videoId']}"
                if platform.domain == "music.youtube.com"
                else platform.get_url(search_query)
            )
            
            button = discord.ui.Button(
                label=platform.name,
                style=discord.ButtonStyle.link,
                url=url,
                emoji=platform.emoji,
                row=1
            )
            self.add_item(button)
    
    def _add_navigation_buttons(self):
        nav_buttons = [
            ("◀️ Назад к поиску", None, discord.ButtonStyle.secondary, self.back_callback),
            ("✅ ПОДТВЕРДИТЬ", None, discord.ButtonStyle.success, self.confirm_callback)
        ]
        
        for label, emoji, style, callback in nav_buttons:
            button = discord.ui.Button(
                label=label,
                style=style,
                custom_id=callback.__name__,
                row=4
            )
            button.callback = callback
            self.add_item(button)

    async def confirm_callback(self, interaction: discord.Interaction):
        try:
            vortex_user = await tryGetOtherUser(interaction.user, interaction)
            if not vortex_user:
                await interaction.response.send_message(
                    "Для использования этой команды необходимо связать свой Steam аккаунт. Используйте команду /link",
                    ephemeral=True
                )
                return
                
            steam_id = vortex_user['steamId']
            track_url = f"https://music.youtube.com/watch?v={self.track['videoId']}"
            
            track_title = f"{self.track['title']} - {', '.join(artist['name'] for artist in self.track['artists'])}"
            cleaned_title = TrackUtils.clean_track_name(track_title)
            
            if not await music_converter.add_to_queue(steam_id, track_url, cleaned_title):
                await interaction.response.send_message(
                    "Произошла ошибка при добавлении трека в очередь. Пожалуйста, попробуйте позже.",
                    ephemeral=True
                )
                return

            track_data = {
                "soundname": cleaned_title,
                "path": "",
                "url": track_url,
                "timestamp": discord.utils.utcnow().isoformat()
            }
            
            if not await music_converter.save_track_data(steam_id, track_data):
                await interaction.response.send_message(
                    "Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.",
                    ephemeral=True
                )
                return
            
            confirm_embed = TrackUtils.create_track_embed(
                title="✨ Трек появится в новом сезоне!",
                track_name=cleaned_title,
                thumbnail_url=self.track['thumbnails'][0]['url']
            )
            confirm_embed.set_footer(text=f"Выбрано {interaction.user.name}")

            platform_links = TrackUtils.get_platform_links(cleaned_title)

            public_embed = discord.Embed(
                title="🎵 Трек нового сезона!",
                color=EMBED_COLOR
            )
            public_embed.description = (
                f"**{cleaned_title}**\n\n"
                f"Выбрал игрок {interaction.user.mention}\n\n{' • '.join(platform_links)}"
            )
            public_embed.set_thumbnail(url=self.track['thumbnails'][0]['url'])

            await interaction.response.edit_message(embed=confirm_embed, view=None)
            await interaction.channel.send(embed=public_embed)

            logger.info(f'Added track for next season for user {steam_id} ({interaction.user.name}): {cleaned_title}')
            
        except Exception as e:
            logger.error(f'Error saving track choice: {str(e)}')
            await interaction.response.send_message(
                "Произошла ошибка при сохранении выбора. Пожалуйста, попробуйте позже.",
                ephemeral=True
            )
    
    async def back_callback(self, interaction: discord.Interaction):
        embed = TrackUtils.create_track_embed(
            title="🔍 Результаты поиска",
            track_name="Выберите трек из списка:"
        )
        
        search_view = TrackSelectView(self.tracks, self.ytmusic, self.bot)
        await interaction.response.edit_message(embed=embed, view=search_view)


class TrackSearchModal(discord.ui.Modal, title="🎵 Поиск трека"):
    query = discord.ui.TextInput(
        label="Название или ссылка на трек",
        placeholder="Название или ссылка из любого сервиса",
        required=True,
        max_length=200,
        style=discord.TextStyle.short
    )
    
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            ytmusic = YTMusic()
            query_text = str(self.query)

            embed = TrackUtils.create_track_embed(
                title="🔍 Результаты поиска",
                track_name=""
            )
            
            is_youtube_url = TrackUtils.is_youtube_url(query_text)
            is_music_youtube_url = "music.youtube.com" in query_text.lower()
            is_other_platform_url = any(platform.domain in query_text.lower() for platform in [
                platform for platform in TrackUtils.MUSIC_PLATFORMS.values() 
                if platform.domain not in ["music.youtube.com", "youtube.com"]
            ])
            
            if is_youtube_url or is_music_youtube_url:
                video_id = TrackUtils.extract_youtube_id(query_text)
                if not video_id:
                    embed.description = "❌ Не удалось обработать ссылку. Пожалуйста, проверьте ссылку и попробуйте снова."
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                
                try:
                    track_info = None
                    try:
                        track_info = ytmusic.get_song(video_id)
                    except Exception as e:
                        logger.warning(f"Не удалось получить информацию через YTMusic API: {str(e)}")
                    
                    if not track_info or 'videoDetails' not in track_info:
                        api_url = f"https://www.youtube.com/watch?v={video_id}"
                        track_info = await get_track_info_from_url(api_url)
                        
                        if not track_info:
                            embed.description = "❌ Не удалось получить информацию о треке. Попробуйте ввести название вручную."
                            await interaction.followup.send(embed=embed, ephemeral=True)
                            return
                            
                        title, artist = track_info
                        
                        vortex_user = await tryGetOtherUser(interaction.user, interaction)
                        if not vortex_user:
                            await interaction.followup.send(
                                "Для использования этой команды необходимо связать свой Steam аккаунт. Используйте команду /link",
                                ephemeral=True
                            )
                            return
                            
                        steam_id = vortex_user['steamId']
                        track_url = f"https://www.youtube.com/watch?v={video_id}"
                        
                        track_title = f"{title}" if not artist else f"{title} - {artist}"
                        cleaned_title = TrackUtils.clean_track_name(track_title)
                        
                        thumbnail_url = await TrackUtils.get_youtube_thumbnail(track_url)
                        
                        if not await music_converter.add_to_queue(steam_id, track_url, cleaned_title):
                            await interaction.followup.send(
                                "Произошла ошибка при добавлении трека в очередь. Пожалуйста, попробуйте позже.",
                                ephemeral=True
                            )
                            return
                        
                        track_data = {
                            "soundname": cleaned_title,
                            "path": "",
                            "url": track_url,
                            "timestamp": discord.utils.utcnow().isoformat()
                        }
                        
                        if not await music_converter.save_track_data(steam_id, track_data):
                            await interaction.followup.send(
                                "Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.",
                                ephemeral=True
                            )
                            return
                        
                        confirm_embed = TrackUtils.create_track_embed(
                            title="✨ Трек появится в новом сезоне!",
                            track_name=cleaned_title,
                            thumbnail_url=thumbnail_url
                        )
                        confirm_embed.set_footer(text=f"Выбрано {interaction.user.name}")
                        
                        platform_links = TrackUtils.get_platform_links(cleaned_title)
                        
                        public_embed = discord.Embed(
                            title="🎵 Трек нового сезона!",
                            color=EMBED_COLOR
                        )
                        public_embed.description = (
                            f"**{cleaned_title}**\n\n"
                            f"Выбрал игрок {interaction.user.mention}\n\n{' • '.join(platform_links)}"
                        )
                        
                        if thumbnail_url:
                            public_embed.set_thumbnail(url=thumbnail_url)
                        
                        await interaction.followup.send(embed=confirm_embed, ephemeral=True)
                        await interaction.channel.send(embed=public_embed)
                        
                        logger.info(f'Added track from YouTube URL for user {steam_id} ({interaction.user.name}): {cleaned_title}')
                        return
                    
                    video_details = track_info['videoDetails']
                    track = {
                        'videoId': video_id,
                        'title': video_details['title'],
                        'artists': [{'name': video_details['author']}],
                        'thumbnails': [{'url': video_details['thumbnail']['thumbnails'][-1]['url']}]
                    }
                    
                    embed = TrackUtils.create_track_embed(
                        title="🎧 Предпрослушивание",
                        track_name=f"{track['title']}\n*{track['artists'][0]['name']}*",
                        thumbnail_url=track['thumbnails'][0]['url']
                    )
                    
                    preview_view = TrackPreviewView(track, [track], ytmusic, self.bot)
                    await interaction.followup.send(embed=embed, view=preview_view, ephemeral=True)
                    return
                    
                except Exception as e:
                    logger.error(f"Ошибка при обработке YouTube ссылки: {str(e)}")
                    embed.description = f"❌ Ошибка при обработке ссылки: {str(e)}"
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            
            elif is_other_platform_url:
                track_info = await get_track_info_from_url(query_text)
                
                if track_info:
                    title, artist = track_info
                    search_query = f"{title} {artist}".strip()
                    logger.info(f'Searching for track: {search_query}')
                    
                    search_results = ytmusic.search(search_query, filter="songs", limit=5)
                    
                    if search_results:
                        embed.description = f"Найдено для: **{search_query}**"
                        view = TrackSelectView(search_results, ytmusic, self.bot)
                        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                        return
                
                embed.description = "❌ Не удалось найти трек. Попробуйте ввести название вручную."
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            search_results = ytmusic.search(query_text, filter="songs", limit=5)
            
            if not search_results:
                embed.description = "❌ По вашему запросу ничего не найдено."
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
                
            view = TrackSelectView(search_results, ytmusic, self.bot)
            embed.description = "Выберите трек из списка:"
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            logger.error(f'Error during track search: {str(e)}')
            embed = TrackUtils.create_track_embed(
                title="❌ Ошибка",
                track_name="Произошла ошибка при поиске. Пожалуйста, попробуйте позже.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


def create_navigation_view(
    callback_pairs: List[Tuple[str, str, discord.ButtonStyle, Callable]],
    row: int = 1
) -> discord.ui.View:
    view = discord.ui.View()
    for label, emoji, style, callback in callback_pairs:
        button = discord.ui.Button(
            label=label,
            emoji=emoji,
            style=style,
            row=row
        )
        button.callback = callback
        view.add_item(button)
    return view