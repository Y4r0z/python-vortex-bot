import discord
import json
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urlparse, quote
import requests
from discord import app_commands
from discord.ext import commands
from ytmusicapi import YTMusic
from lib.vortex_api import GetPlayerTrack, UpdatePlayerTrack, PlayerMusic, PlayerMusicInput
from tools.ds import tryGetOtherUser
import settings

logger = settings.logging.getLogger("discord")
EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)  # Discord Blurple

class NextSeasonTrackManager:
    def __init__(self, bot: commands.Bot):
        self.tracks_file = 'preferences/tracks.json'
        self.bot = bot
        
    async def can_set_track(self) -> bool:
        """Проверяет, можно ли сейчас установить трек на следующий сезон"""
        now = datetime.utcnow()
        return 20 <= now.day <= 30
        
    async def get_next_season_track(self, steam_id: str) -> Optional[Dict[str, Any]]:
        """Получает трек пользователя на следующий сезон"""
        if not os.path.exists(self.tracks_file):
            return None
            
        try:
            with open(self.tracks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(steam_id)
        except (json.JSONDecodeError, FileNotFoundError):
            return None
            
    async def set_next_season_track(self, steam_id: str, track_data: Dict[str, Any]) -> bool:
        """Устанавливает трек пользователя на следующий сезон"""
        if not await self.can_set_track():
            return False
            
        try:
            # Создаем директорию если её нет
            os.makedirs(os.path.dirname(self.tracks_file), exist_ok=True)
            
            # Читаем существующие данные или создаем новый словарь
            data = {}
            try:
                if os.path.exists(self.tracks_file):
                    with open(self.tracks_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if content.strip():
                            data = json.loads(content)
            except json.JSONDecodeError:
                data = {}
            
            # Добавляем или обновляем трек пользователя
            data[steam_id] = {
                "soundname": track_data["soundname"],
                "path": track_data.get("path", ""),
                "url": track_data["url"],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Сохраняем обновленные данные
            with open(self.tracks_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
            return True
        except Exception as e:
            logger.error(f"Error saving next season track: {str(e)}")
            return False
            
    async def apply_season_tracks(self) -> bool:
        """Применяет треки следующего сезона в API (вызывается 1 числа)"""
        if datetime.utcnow().day != 1:
            return False
            
        try:
            if not os.path.exists(self.tracks_file):
                return True
                
            with open(self.tracks_file, 'r', encoding='utf-8') as f:
                tracks = json.load(f)
                
            for steam_id, track in tracks.items():
                track_input = PlayerMusicInput(
                    soundname=track["soundname"],
                    path=track.get("path", ""),
                    url=track.get("url")
                )
                await UpdatePlayerTrack(steam_id, track_input)
                
            # Очищаем файл после успешного применения
            os.remove(self.tracks_file)
            return True
        except Exception as e:
            logger.error(f"Error applying season tracks: {str(e)}")
            return False
            
    async def get_current_track(self, steam_id: str) -> Optional[PlayerMusic]:
        """Получает текущий трек пользователя из API"""
        try:
            return await GetPlayerTrack(steam_id)
        except Exception:
            return None

async def get_track_info_from_url(url: str) -> tuple[str, str] | None:
    """
    Получает информацию о треке из URL любого поддерживаемого сервиса
    Returns: tuple(title, artist) или None
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        response = requests.get(url, headers=headers)
        
        # Обработка YouTube Music
        if 'music.youtube.com' in url:
            video_id = url.split('v=')[1].split('&')[0]
            ytmusic = YTMusic()
            track_info = ytmusic.get_song(video_id)
            if track_info and 'videoDetails' in track_info:
                return track_info['videoDetails']['title'], track_info['videoDetails']['author']
        
        # Обработка Spotify
        elif 'spotify.com' in url:
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
            artist_match = re.search(r'<meta property="og:description" content="([^"]+)"', response.text)
            
            if title_match and artist_match:
                title = title_match.group(1)
                artist = artist_match.group(1).split('·')[0].strip()
                return title, artist
        
        # Обработка других сервисов
        else:
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
            if not title_match:
                return None
                
            title = title_match.group(1)
            
            if ' — ' in title:  # Yandex Music
                artist, track = title.split(' — ', 1)
            elif ' – ' in title:  # Некоторые другие сервисы
                artist, track = title.split(' – ', 1)
            elif ' - ' in title:  # Общий случай
                artist, track = title.split(' - ', 1)
            else:
                return title, ""
                
            return track.strip(), artist.strip()
            
    except Exception as e:
        logger.error(f'Error getting track info from URL: {str(e)}')
        return None

class TrackSelectView(discord.ui.View):
    def __init__(self, tracks: list, ytmusic: YTMusic, bot: commands.Bot, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.tracks = tracks
        self.ytmusic = ytmusic
        self.bot = bot
        self.add_track_buttons(tracks[:5])

    def add_track_buttons(self, tracks: list):
        for track in tracks:
            button = discord.ui.Button(
                label=f"{track['title']} - {track['artists'][0]['name']}",
                style=discord.ButtonStyle.secondary,
                custom_id=f"track_{track['videoId']}"
            )
            button.callback = self.track_button_callback
            self.add_item(button)

    async def track_button_callback(self, interaction: discord.Interaction):
        video_id = interaction.data['custom_id'].replace('track_', '')
        track = next(t for t in self.tracks if t['videoId'] == video_id)
        
        embed = discord.Embed(
            title="🎧 Предпрослушивание",
            description=f"**{track['title']}**\n*{track['artists'][0]['name']}*",
            color=EMBED_COLOR
        )
        embed.set_thumbnail(url=track['thumbnails'][0]['url'])
        
        preview_view = TrackPreviewView(track, self.tracks, self.ytmusic, self.bot)
        
        await interaction.response.edit_message(
            embed=embed,
            view=preview_view
        )

class TrackPreviewView(discord.ui.View):
    def __init__(self, track: dict, tracks: list, ytmusic: YTMusic, bot: commands.Bot):
        super().__init__()
        self.track = track
        self.tracks = tracks
        self.ytmusic = ytmusic
        self.bot = bot
        self.track_manager = NextSeasonTrackManager('data/next_season_tracks.json')
        self.add_platform_buttons()
        
    def add_platform_buttons(self):
        search_query = f"{self.track['title']} {self.track['artists'][0]['name']}"
        encoded_query = quote(search_query)
        
        # YouTube Music кнопка
        yt_url = f"https://music.youtube.com/watch?v={self.track['videoId']}"
        yt_button = discord.ui.Button(
            label="YouTube Music",
            style=discord.ButtonStyle.link,
            url=yt_url,
            emoji="🎵",
            row=1
        )
        self.add_item(yt_button)
        
        # Spotify кнопка
        spotify_button = discord.ui.Button(
            label="Spotify",
            style=discord.ButtonStyle.link,
            url=f"https://open.spotify.com/search/{encoded_query}",
            emoji="🟢",
            row=1
        )
        self.add_item(spotify_button)
        
        # Yandex Music кнопка
        yandex_button = discord.ui.Button(
            label="Yandex Music",
            style=discord.ButtonStyle.link,
            url=f"https://music.yandex.ru/search?text={encoded_query}",
            emoji="🎧",
            row=1
        )
        self.add_item(yandex_button)
        
        # Apple Music кнопка
        apple_button = discord.ui.Button(
            label="Apple Music",
            style=discord.ButtonStyle.link,
            url=f"https://music.apple.com/search?term={encoded_query}",
            emoji="🍎",
            row=1
        )
        self.add_item(apple_button)
        
        # Кнопки навигации
        back_button = discord.ui.Button(
            label="◀️ Назад к поиску",
            style=discord.ButtonStyle.secondary,
            custom_id="back",
            row=4
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)
        
        confirm_button = discord.ui.Button(
            label="✅ ПОДТВЕРДИТЬ",
            style=discord.ButtonStyle.success,
            custom_id="confirm",
            row=4
        )
        confirm_button.callback = self.confirm_callback
        self.add_item(confirm_button)
    
    async def confirm_callback(self, interaction: discord.Interaction):
        try:
            # Получаем Steam ID пользователя через Vortex API
            vortex_user = await tryGetOtherUser(interaction.user, interaction)
            if not vortex_user:
                await interaction.response.send_message(
                    "Для использования этой команды необходимо связать свой Steam аккаунт. Используйте команду /link",
                    ephemeral=True
                )
                return
                
            steam_id = vortex_user['steamId']
            track_url = f"https://music.youtube.com/watch?v={self.track['videoId']}"
            track_title = f"{self.track['title']} - {self.track['artists'][0]['name']}"
            
            # Получаем конвертер из когов бота
            converter = self.bot.get_cog('MusicConverterCog')
            if not converter:
                await interaction.response.send_message(
                    "Ошибка: конвертер недоступен. Обратитесь к администратору.",
                    ephemeral=True
                )
                return

            # Добавляем в очередь на конвертацию
            queue_success = await converter.add_to_queue(steam_id, track_url, track_title)
            if not queue_success:
                await interaction.response.send_message(
                    "Произошла ошибка при добавлении трека в очередь. Пожалуйста, попробуйте позже.",
                    ephemeral=True
                )
                return

            # Создаем директорию если её нет
            os.makedirs(os.path.dirname(converter.tracks_file), exist_ok=True)
            
            # Читаем существующие данные или создаем новый словарь
            data = {}
            try:
                if os.path.exists(converter.tracks_file):
                    with open(converter.tracks_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if content.strip():
                            data = json.loads(content)
            except json.JSONDecodeError:
                data = {}
            
            # Обновляем или добавляем данные
            data[steam_id] = {
                "soundname": track_title,
                "path": "",
                "url": track_url,
                "timestamp": discord.utils.utcnow().isoformat()
            }
            
            # Сохраняем обновленные данные
            try:
                with open(converter.tracks_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
            except Exception as e:
                logger.error(f'Error saving to tracks.json: {str(e)}')
                await interaction.response.send_message(
                    "Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.",
                    ephemeral=True
                )
                return
            
            # Создаем эмбед для подтверждения
            embed = discord.Embed(
                title="✨ Любимый трек добавлен в очередь!",
                description=f"**{track_title}**\n{track_url}\n\n*Трек будет обработан в фоновом режиме*",
                color=EMBED_COLOR
            )
            embed.set_thumbnail(url=self.track['thumbnails'][0]['url'])
            embed.set_footer(text=f"Выбрано {interaction.user.name}")
            
            await interaction.response.edit_message(
                embed=embed,
                view=None
            )
            
            # Отправляем публичное сообщение в канал
            search_query = f"{self.track['title']} {self.track['artists'][0]['name']}"
            encoded_query = quote(search_query)
            
            links = [
                f"[🎵 YouTube Music]({track_url})",
                f"[🟢 Spotify](https://open.spotify.com/search/{encoded_query})",
                f"[🎧 Yandex Music](https://music.yandex.ru/search?text={encoded_query})",
                f"[🍎 Apple Music](https://music.apple.com/search?term={encoded_query})"
            ]
            
            public_embed = discord.Embed(
                title="🎵 Новый трек на следующий сезон!",
                description=f"{interaction.user.mention} выбрал:\n**{track_title}**\n\n{' • '.join(links)}",
                color=EMBED_COLOR
            )
            public_embed.set_thumbnail(url=self.track['thumbnails'][0]['url'])
            
            await interaction.channel.send(embed=public_embed)
            
            logger.info(f'Added track for next season for user {steam_id} ({interaction.user.name}): {track_title}')
            
        except Exception as e:
            logger.error(f'Error saving track choice: {str(e)}')
            await interaction.response.send_message(
                "Произошла ошибка при сохранении выбора. Пожалуйста, попробуйте позже.",
                ephemeral=True
            )
    
    async def back_callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🔍 Результаты поиска",
            description="Выберите трек из списка:",
            color=EMBED_COLOR
        )
        
        search_view = TrackSelectView(self.tracks, self.ytmusic, self.bot)
        
        await interaction.response.edit_message(
            embed=embed,
            view=search_view
        )

class TrackSearchModal(discord.ui.Modal, title="🎵 Поиск трека"):
    query = discord.ui.TextInput(
        label="Название или ссылка на трек",
        placeholder="Введите название или вставьте ссылку из любого музыкального сервиса",
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
            
            embed = discord.Embed(
                title="🔍 Результаты поиска",
                color=EMBED_COLOR
            )
            
            if any(service in query_text.lower() for service in ['music.youtube.com', 'music.yandex', 'music.apple.com', 'spotify.com']):
                track_info = await get_track_info_from_url(query_text)
                
                if track_info:
                    title, artist = track_info
                    search_query = f"{title} {artist}".strip()
                    logger.info(f'Searching for track: {search_query}')
                    
                    search_results = ytmusic.search(search_query, filter="songs", limit=5)
                    
                    if search_results:
                        embed.description = f"Найдено для: **{search_query}**"
                        view = TrackSelectView(search_results, ytmusic, self.bot)
                        await interaction.followup.send(
                            embed=embed,
                            view=view,
                            ephemeral=True
                        )
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
            await interaction.followup.send(
                embed=embed,
                view=view,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f'Error during track search: {str(e)}')
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла ошибка при поиске. Пожалуйста, попробуйте позже.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

class MyTrackCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.track_manager = NextSeasonTrackManager(bot)
        super().__init__()

    async def show_current_track(self, interaction: discord.Interaction, steam_id: str) -> None:
        """Показывает текущий трек пользователя"""
        current_track = await self.track_manager.get_current_track(steam_id)
        if not current_track:
            await self.show_no_track_message(interaction)
            return
            
        # Создаем эмбед с текущим треком
        embed = discord.Embed(
            title="🎵 Ваш текущий трек",
            description=f"**{current_track['soundname']}**\n\n"
                       f"Воспроизведений: **{current_track['playcount']:,}**",
            color=EMBED_COLOR
        )
        
        # Добавляем картинку, если доступна
        if current_track.get('url') and 'youtube.com' in current_track['url']:
            try:
                ytmusic = YTMusic()
                video_id = current_track['url'].split('v=')[1].split('&')[0]
                track_info = ytmusic.get_song(video_id)
                if track_info and 'videoDetails' in track_info:
                    thumbnail = track_info['videoDetails']['thumbnail']['thumbnails'][-1]['url']
                    embed.set_thumbnail(url=thumbnail)
            except Exception as e:
                logger.error(f'Error getting track thumbnail: {str(e)}')
        
        # Добавляем ссылки на музыкальные сервисы
        if current_track.get('url'):
            search_query = quote(current_track['soundname'])
            links = [
                f"[🎵 YouTube Music]({current_track['url']})",
                f"[🟢 Spotify](https://open.spotify.com/search/{search_query})",
                f"[🎧 Yandex Music](https://music.yandex.ru/search?text={search_query})",
                f"[🍎 Apple Music](https://music.apple.com/search?term={search_query})"
            ]
            embed.add_field(name="Слушать:", value=" • ".join(links), inline=False)
            
        # Создаем кнопки
        view = discord.ui.View()
        
        # Кнопка для следующего сезона
        next_season_button = discord.ui.Button(
            label="Трек следующего сезона",
            style=discord.ButtonStyle.secondary,
            emoji="⏭️",
            row=1
        )
        async def next_season_callback(inter: discord.Interaction):
            await self.show_next_season_track(inter, steam_id)
        next_season_button.callback = next_season_callback
        view.add_item(next_season_button)
        
        # Кнопка для публичного показа
        share_button = discord.ui.Button(
            label="Поделиться",
            style=discord.ButtonStyle.success,
            emoji="📢",
            row=1
        )
        async def share_callback(inter: discord.Interaction):
            public_embed = discord.Embed(
                title="🎵 Любимый трек!",
                description=f"{inter.user.mention} слушает:\n**{current_track['soundname']}**\n\n"
                           f"Количество прослушиваний: **{current_track['playcount']:,}**\n\n"
                           f"{' • '.join(links)}",
                color=EMBED_COLOR
            )
            if embed.thumbnail:
                public_embed.set_thumbnail(url=embed.thumbnail.url)
            await inter.response.send_message(embed=public_embed)
            
        share_button.callback = share_callback
        view.add_item(share_button)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_next_season_track(self, interaction: discord.Interaction, steam_id: str) -> None:
        """Показывает трек пользователя на следующий сезон"""
        next_track = await self.track_manager.get_next_season_track(steam_id)
        
        if not next_track:
            can_set = await self.track_manager.can_set_track()
            if can_set:
                await self.show_no_track_message(interaction, is_next_season=True)
            else:
                embed = discord.Embed(
                    title="⏭️ Трек следующего сезона",
                    description="Установка трека на следующий сезон доступна с 20 по 30 число каждого месяца.",
                    color=EMBED_COLOR
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        # Создаем эмбед с треком следующего сезона
        embed = discord.Embed(
            title="⏭️ Ваш трек на следующий сезон",
            description=f"**{next_track['soundname']}**",
            color=EMBED_COLOR
        )
        
        # Получаем thumbnail, если это YouTube Music
        if next_track.get('url') and 'youtube.com' in next_track['url']:
            try:
                ytmusic = YTMusic()
                video_id = next_track['url'].split('v=')[1].split('&')[0]
                track_info = ytmusic.get_song(video_id)
                if track_info and 'videoDetails' in track_info:
                    thumbnail = track_info['videoDetails']['thumbnail']['thumbnails'][-1]['url']
                    embed.set_thumbnail(url=thumbnail)
            except Exception as e:
                logger.error(f'Error getting track thumbnail: {str(e)}')
        
        search_query = quote(next_track['soundname'])
        links = [
            f"[🎵 YouTube Music]({next_track['url']})",
            f"[🟢 Spotify](https://open.spotify.com/search/{search_query})",
            f"[🎧 Yandex Music](https://music.yandex.ru/search?text={search_query})",
            f"[🍎 Apple Music](https://music.apple.com/search?term={search_query})"
        ]
        embed.add_field(name="Слушать:", value=" • ".join(links), inline=False)
        embed.set_footer(text="Вы можете изменить трек, нажав кнопку ниже")
        
        # Создаем кнопки
        view = discord.ui.View()
        
        # Кнопка изменения трека
        change_button = discord.ui.Button(
            label="Изменить трек",
            style=discord.ButtonStyle.primary,
            emoji="🔄",
            row=1
        )
        
        async def change_callback(inter: discord.Interaction):
            modal = TrackSearchModal(self.bot)
            await inter.response.send_modal(modal)
            
        change_button.callback = change_callback
        view.add_item(change_button)
        
        # Кнопка возврата к текущему треку
        back_button = discord.ui.Button(
            label="Текущий трек",
            style=discord.ButtonStyle.secondary,
            emoji="◀️",
            row=1
        )
        
        async def back_callback(inter: discord.Interaction):
            await self.show_current_track(inter, steam_id)
            
        back_button.callback = back_callback
        view.add_item(back_button)
        
        # Кнопка для публичного показа
        share_button = discord.ui.Button(
            label="Поделиться",
            style=discord.ButtonStyle.success,
            emoji="📢",
            row=1
        )
        
        async def share_callback(inter: discord.Interaction):
            public_embed = discord.Embed(
                title="⏭️ Трек на следующий сезон!",
                description=f"{inter.user.mention} выбрал:\n**{next_track['soundname']}**\n\n"
                           f"{' • '.join(links)}",
                color=EMBED_COLOR
            )
            if embed.thumbnail:
                public_embed.set_thumbnail(url=embed.thumbnail.url)
            await inter.response.send_message(embed=public_embed)
            
        share_button.callback = share_callback
        view.add_item(share_button)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_no_track_message(self, interaction: discord.Interaction, is_next_season: bool = False) -> None:
        """Показывает сообщение о том, что трек не установлен"""
        title = "⏭️ Трек следующего сезона" if is_next_season else "🎵 Любимый трек"
        embed = discord.Embed(
            title=title,
            description="У вас пока нет установленного трека. Нажмите кнопку ниже, чтобы добавить его!",
            color=EMBED_COLOR
        )
        
        view = discord.ui.View()
        search_button = discord.ui.Button(
            label="Искать трек",
            style=discord.ButtonStyle.primary,
            emoji="🔍"
        )
        
        async def search_button_callback(inter: discord.Interaction):
            modal = TrackSearchModal(self.bot)
            await inter.response.send_modal(modal)
            
        search_button.callback = search_button_callback
        view.add_item(search_button)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(
        name='mytrack',
        description='🎵 Установить любимый трек (поддерживает ссылки из разных сервисов)'
    )
    async def mytrack(self, interaction: discord.Interaction) -> None:
        logger.info(f'MyTrack command called by {interaction.user.id} ({interaction.user.name})')
        try:
            # Получаем Steam ID пользователя
            vortex_user = await tryGetOtherUser(interaction.user, interaction)
            if not vortex_user:
                await interaction.response.send_message(
                    "Для использования этой команды необходимо связать свой Steam аккаунт. Используйте команду /link",
                    ephemeral=True
                )
                return
                
            steam_id = vortex_user['steamId']
            
            # Проверяем текущий трек
            current_track = await self.track_manager.get_current_track(steam_id)
            if current_track:
                await self.show_current_track(interaction, steam_id)
            else:
                await self.show_no_track_message(interaction)
                
        except Exception as e:
            logger.error(f'Unexpected error in mytrack command: {str(e)}')
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(
        MyTrackCommand(bot),
        guild=discord.Object(id=settings.GUILD_ID)
    )