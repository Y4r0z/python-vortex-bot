import discord
import json
import os
import re
import requests
import settings
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Callable
from urllib.parse import quote
from discord import app_commands
from discord.ext import commands
from ytmusicapi import YTMusic
from lib.vortex_api import GetPlayerTrack, PlayerMusic
from tools.ds import tryGetOtherUser

logger = settings.logging.getLogger("discord")
EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)  # Discord Blurple

class MusicPlatform:
    def __init__(self, name: str, emoji: str, url_template: str, domain: str = None):
        self.name = name
        self.emoji = emoji
        self.url_template = url_template
        self.domain = domain or ""
    
    def get_url(self, query: str) -> str:
        return self.url_template.format(query=quote(query))
    
    def get_link_markdown(self, query: str) -> str:
        return f"[{self.emoji} {self.name}]({self.get_url(query)})"

class TrackUtils:
    MUSIC_PLATFORMS = {
        'youtube': MusicPlatform(
            name="YouTube",
            emoji="<:youtubemusic:1330994676471173201>",
            url_template="https://music.youtube.com/watch?v={query}",
            domain="music.youtube.com"
        ),
        'spotify': MusicPlatform(
            name="Spotify",
            emoji="<:spotify:1330994601624076298>",
            url_template="https://open.spotify.com/search/{query}",
            domain="spotify.com"
        ),
        'yandex': MusicPlatform(
            name="Yandex",
            emoji="<:yandexmusic:1330994641641672815>",
            url_template="https://music.yandex.ru/search?text={query}",
            domain="music.yandex"
        ),
        'apple': MusicPlatform(
            name="Apple",
            emoji="<:applemusic:1330996067117957220>",
            url_template="https://music.apple.com/search?term={query}",
            domain="music.apple.com"
        )
    }

    @staticmethod
    def get_platform_links(query: str) -> List[str]:
        """Возвращает список markdown-ссылок на все музыкальные платформы"""
        return [platform.get_link_markdown(query) for platform in TrackUtils.MUSIC_PLATFORMS.values()]
    
    @staticmethod
    def create_track_embed(
        title: str,
        track_name: str,
        thumbnail_url: str = None,
        color: discord.Color = EMBED_COLOR,
        **kwargs
    ) -> discord.Embed:
        """Создает стандартный эмбед для трека"""
        embed = discord.Embed(title=title, color=color)
        embed.description = f"**{track_name}**"
        
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
            
        for name, value in kwargs.items():
            if value:
                embed.add_field(name=name, value=value, inline=False)
                
        return embed
    
    @staticmethod
    def create_navigation_view(
        callback_pairs: List[Tuple[str, str, discord.ButtonStyle, Callable]],
        row: int = 1
    ) -> discord.ui.View:
        """Создает view с навигационными кнопками"""
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

    @staticmethod
    async def get_youtube_thumbnail(url: str) -> Optional[str]:
        """Получает thumbnail для YouTube Music трека"""
        try:
            if 'youtube.com' not in url:
                return None
                
            ytmusic = YTMusic()
            video_id = url.split('v=')[1].split('&')[0]
            track_info = ytmusic.get_song(video_id)
            
            if track_info and 'videoDetails' in track_info:
                return track_info['videoDetails']['thumbnail']['thumbnails'][-1]['url']
        except Exception as e:
            logger.error(f'Error getting track thumbnail: {str(e)}')
        return None

class NextSeasonTrackManager:
    def __init__(self, bot: commands.Bot):
        self.tracks_file = 'preferences/tracks.json'
        self.bot = bot
        
    async def can_set_track(self) -> bool:
        """Проверяет, можно ли сейчас установить трек на следующий сезон"""
        now = datetime.utcnow()
        return 0 <= now.day
        
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
            os.makedirs(os.path.dirname(self.tracks_file), exist_ok=True)
            
            data = {}
            try:
                if os.path.exists(self.tracks_file):
                    with open(self.tracks_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if content.strip():
                            data = json.loads(content)
            except json.JSONDecodeError:
                data = {}
            
            data[steam_id] = {
                "soundname": track_data["soundname"],
                "path": track_data.get("path", ""),
                "url": track_data["url"],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            with open(self.tracks_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                
            return True
        except Exception as e:
            logger.error(f"Error saving next season track: {str(e)}")
            return False
            
    async def get_current_track(self, steam_id: str) -> Optional[PlayerMusic]:
        """Получает текущий трек пользователя из API"""
        try:
            return await GetPlayerTrack(steam_id)
        except Exception as e:
            logger.error(f"Error getting current track: {str(e)}")
            return None
        


async def get_track_info_from_url(url: str) -> Optional[Tuple[str, str]]:
    """
    Получает информацию о треке из URL любого поддерживаемого сервиса.
    Декодирует HTML-сущности и очищает текст от специальных символов для лучшего поиска.
    
    Returns: tuple(title, artist) или None
    """
    try:
        from html import unescape
        import re
        
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }
        response = requests.get(url, headers=headers)
        
        def clean_search_text(text: str) -> str:
            """
            Очищает текст от HTML-сущностей и спецсимволов.
            Также удаляет суффиксы вида " on Service Name"
            """
            # Декодируем HTML-сущности
            text = unescape(text)
            
            # Удаляем всё после " on " (с пробелами)
            if " on " in text:
                text = text.split(" on ")[0]
            
            # Удаляем " by " и всё после (только если это в конце строки)
            if text.endswith(")"):
                # Если строка заканчивается на ')', сохраняем скобки
                base = text[:-1]
                if " by " in base:
                    text = base.split(" by ")[0] + ")"
            else:
                if " by " in text:
                    text = text.split(" by ")[0]
            
            return text.strip()
        
        if 'music.youtube.com' in url:
            video_id = url.split('v=')[1].split('&')[0]
            ytmusic = YTMusic()
            track_info = ytmusic.get_song(video_id)
            if track_info and 'videoDetails' in track_info:
                title = clean_search_text(track_info['videoDetails']['title'])
                artist = clean_search_text(track_info['videoDetails']['author'])
                return title, artist
        
        elif 'spotify.com' in url:
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
            artist_match = re.search(r'<meta property="og:description" content="([^"]+)"', response.text)
            
            if title_match and artist_match:
                title = clean_search_text(title_match.group(1))
                artist = clean_search_text(artist_match.group(1).split('·')[0])
                return title, artist

        elif 'music.yandex' in url:
            # Yandex Music использует JSON-данные в теге script
            json_match = re.search(r'<script type="application/ld\+json">(.+?)</script>', response.text)
            if json_match:
                try:
                    track_data = json.loads(json_match.group(1))
                    if isinstance(track_data, list):
                        track_data = track_data[0]
                    
                    if 'name' in track_data and 'byArtist' in track_data:
                        title = clean_search_text(track_data['name'])
                        if isinstance(track_data['byArtist'], list):
                            artist = clean_search_text(track_data['byArtist'][0]['name'])
                        else:
                            artist = clean_search_text(track_data['byArtist']['name'])
                        return title, artist
                except json.JSONDecodeError:
                    pass

            # Запасной вариант через мета-теги
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
            if title_match:
                title = clean_search_text(title_match.group(1))
                # Yandex Music обычно использует формат "Исполнитель - Название"
                if ' - ' in title:
                    artist, track = title.split(' - ', 1)
                    return clean_search_text(track), clean_search_text(artist)

        elif 'music.apple.com' in url:
            # Apple Music использует JSON-данные в теге script
            json_match = re.search(r'<script type="application/ld\+json">(.+?)</script>', response.text)
            if json_match:
                try:
                    track_data = json.loads(json_match.group(1))
                    if 'name' in track_data and 'byArtist' in track_data:
                        title = clean_search_text(track_data['name'])
                        if isinstance(track_data['byArtist'], list):
                            artist = clean_search_text(track_data['byArtist'][0]['name'])
                        else:
                            artist = clean_search_text(track_data['byArtist']['name'])
                        return title, artist
                except json.JSONDecodeError:
                    pass
            
            # Запасной вариант через мета-теги
            title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
            desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', response.text)
            
            if title_match and desc_match:
                title = clean_search_text(title_match.group(1))
                description = clean_search_text(desc_match.group(1))
                # Извлекаем имя исполнителя из описания
                artist_match = re.search(r'Song · (.+?) ·', description)
                if artist_match:
                    artist = clean_search_text(artist_match.group(1))
                    return title, artist
        
        # Для остальных сервисов пытаемся извлечь из og:title
        title_match = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
        if not title_match:
            return None
            
        title = clean_search_text(title_match.group(1))
        
        for separator in [' — ', ' – ', ' - ']:
            if separator in title:
                artist, track = title.split(separator, 1)
                return clean_search_text(track), clean_search_text(artist)
                
        return title, ""
            
    except Exception as e:
        logger.error(f'Error getting track info from URL: {str(e)}')
        return None

class TrackSelectView(discord.ui.View):
    def __init__(self, tracks: list, ytmusic: YTMusic, bot: commands.Bot, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.tracks = tracks
        self.ytmusic = ytmusic
        self.bot = bot
        self._add_track_buttons()

    def _truncate_text(self, text: str, max_length: int = 75) -> str:
        """Сокращает текст до указанной длины, добавляя ... если текст был обрезан"""
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    def _add_track_buttons(self):
        """Добавляет кнопки с треками"""
        for track in self.tracks[:5]:
            # Формируем текст для кнопки и обрезаем его при необходимости
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
        """Добавляет кнопки музыкальных платформ"""
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
        """Добавляет кнопки навигации"""
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

    @staticmethod
    def clean_track_name(title: str) -> str:
        """
        Очищает название трека от информации в скобках и лишних авторов.
        
        Args:
            title (str): Исходное название трека
            
        Returns:
            str: Очищенное название трека
        """
        import re
        
        # Паттерн для поиска скобок и их содержимого
        brackets_pattern = r'\s*[\(\[\{].*?[\)\]\}]'
        
        # Сначала удаляем все скобки и их содержимое
        cleaned = re.sub(brackets_pattern, '', title)
        
        # Разделяем название и авторов
        if ' - ' in cleaned:
            song_part, artists_part = cleaned.split(' - ', 1)
            
            # Берем только первого автора до запятой
            first_artist = artists_part.split(',')[0].strip()
            
            # Собираем очищенное название
            cleaned = f"{song_part.strip()} - {first_artist}"
        
        # Удаляем лишние пробелы
        cleaned = ' '.join(cleaned.split())
        
        return cleaned

    # Для использования в TrackPreviewView необходимо изменить метод confirm_callback:
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
            
            # Собираем полное название с авторами и очищаем его
            track_title = f"{self.track['title']} - {', '.join(artist['name'] for artist in self.track['artists'])}"
            cleaned_title = self.clean_track_name(track_title)
            
            # Получаем конвертер
            converter = self.bot.get_cog('MusicConverterCog')
            if not converter:
                await interaction.response.send_message(
                    "Ошибка: конвертер недоступен. Обратитесь к администратору.",
                    ephemeral=True
                )
                return

            # Добавляем в очередь (используем очищенное название)
            if not await converter.add_to_queue(steam_id, track_url, cleaned_title):
                await interaction.response.send_message(
                    "Произошла ошибка при добавлении трека в очередь. Пожалуйста, попробуйте позже.",
                    ephemeral=True
                )
                return

            # Сохраняем данные с очищенным названием
            track_data = {
                "soundname": cleaned_title,
                "path": "",
                "url": track_url,
                "timestamp": discord.utils.utcnow().isoformat()
            }
            
            if not await converter.save_track_data(steam_id, track_data):
                await interaction.response.send_message(
                    "Произошла ошибка при сохранении данных. Пожалуйста, попробуйте позже.",
                    ephemeral=True
                )
                return
            
            # Используем очищенное название для эмбедов
            confirm_embed = TrackUtils.create_track_embed(
                title="✨ Трек появится в новом сезоне!",
                track_name=cleaned_title,
                thumbnail_url=self.track['thumbnails'][0]['url']
            )
            confirm_embed.set_footer(text=f"Выбрано {interaction.user.name}")

            # Генерация ссылок на платформы также с очищенным названием
            platform_links = TrackUtils.get_platform_links(cleaned_title)

            # Создаем public_embed с очищенным названием
            public_embed = discord.Embed(
                title="🎵 Трек нового сезона!",
                color=EMBED_COLOR
            )
            public_embed.description = (
                f"**{cleaned_title}**\n\n"
                f"Выбрал игрок {interaction.user.mention}\n\n{' • '.join(platform_links)}"
            )
            public_embed.set_thumbnail(url=self.track['thumbnails'][0]['url'])

            # Отправляем сообщения
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
            
            # Проверяем, является ли запрос ссылкой
            if any(platform.domain in query_text.lower() for platform in TrackUtils.MUSIC_PLATFORMS.values()):
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
            
            # Поиск по названию
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

def load_role_ids():
    """Загружает ID ролей из конфигурационного файла"""
    try:
        with open('preferences/ids.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f'Error loading role IDs: {str(e)}')
        return {}

def check_roles():
    """Декоратор для проверки ролей пользователя"""
    async def predicate(interaction: discord.Interaction) -> bool:
        # Проверяем, является ли пользователь администратором
        if interaction.user.guild_permissions.administrator:
            return True
            
        role_ids = load_role_ids()
        allowed_roles = {
            role_ids.get('moder_role_id'),
            role_ids.get('legend_role_id')
        }
        
        # Убираем None из множества
        allowed_roles = {role_id for role_id in allowed_roles if role_id is not None}
        
        # Проверяем наличие разрешенных ролей у пользователя
        user_roles = {role.id for role in interaction.user.roles}
        if any(role_id in user_roles for role_id in allowed_roles):
            return True
            
        # Если нет нужных ролей, отправляем сообщение об ошибке
        await interaction.response.send_message(
            "У вас недостаточно прав для использования этой команды.",
            ephemeral=True
        )
        return False
        
    return app_commands.check(predicate)

class MyTrackCommand(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.track_manager = NextSeasonTrackManager(bot)
        super().__init__()

    @app_commands.command(
        name='mytrack',
        description='🎵 Установить любимый трек (поддерживает ссылки из разных сервисов)'
    )
    @check_roles()
    async def mytrack(self, interaction: discord.Interaction) -> None:
        """Обработчик команды /mytrack"""
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
                current_track = await self.track_manager.get_current_track(steam_id)
                await self.show_current_track(interaction, steam_id)
            except Exception as api_error:
                # В случае ошибки API (включая 404) показываем трек следующего сезона
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
        """Показывает текущий трек пользователя"""
        try:
            current_track = await self.track_manager.get_current_track(steam_id)
            if not current_track:
                await self.show_next_season_track(interaction, steam_id)
                return

            # Получаем thumbnail для YouTube Music
            thumbnail_url = await TrackUtils.get_youtube_thumbnail(current_track.get('url', ''))

            # Создаем эмбед
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

            # Создаем навигационные кнопки
            view = TrackUtils.create_navigation_view([
                ("Трек следующего сезона", "⏭️", discord.ButtonStyle.secondary, 
                 lambda i: self.show_next_season_track(i, steam_id)),
                ("Поделиться", "📢", discord.ButtonStyle.success,
                 lambda i: self.share_track(i, embed, current_track))
            ])

            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            # В случае любой ошибки показываем трек следующего сезона
            logger.warning(f'Error showing current track for {steam_id}: {str(e)}')
            await self.show_next_season_track(interaction, steam_id)

    async def show_next_season_track(self, interaction: discord.Interaction, steam_id: str) -> None:
        """Показывает трек пользователя на следующий сезон"""
        next_track = await self.track_manager.get_next_season_track(steam_id)
        
        if not next_track:
            can_set = await self.track_manager.can_set_track()
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
        
        # Получаем thumbnail
        thumbnail_url = await TrackUtils.get_youtube_thumbnail(next_track.get('url', ''))
        
        # Создаем эмбед
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
        
        # Создаем кнопки
        view = TrackUtils.create_navigation_view([
            ("Изменить трек", "🔄", discord.ButtonStyle.primary, 
             lambda i: self._show_track_search_modal(i)),
            ("Текущий трек", "◀️", discord.ButtonStyle.secondary,
             lambda i: self.show_current_track(i, steam_id)),
        ])

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def _show_track_search_modal(self, interaction: discord.Interaction) -> None:
        """Показывает модальное окно поиска трека"""
        modal = TrackSearchModal(self.bot)
        await interaction.response.send_modal(modal)

    async def show_no_track_message(self, interaction: discord.Interaction, is_next_season: bool = False) -> None:
        """Показывает сообщение о том, что трек не установлен"""
        title = "⏭️ Трек следующего сезона" if is_next_season else "🎵 Любимый трек"
        
        embed = discord.Embed(color=EMBED_COLOR)
        embed.description = (
            f"**{title}**\n"
            f"### У вас пока нет установленного трека. Нажмите кнопку ниже, чтобы добавить его!"
        )
        
        view = TrackUtils.create_navigation_view([
            ("Искать трек", "🔍", discord.ButtonStyle.primary, 
             lambda i: self._show_track_search_modal(i))
        ])
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def share_track(
        self, 
        interaction: discord.Interaction, 
        source_embed: discord.Embed,
        track_data: Dict[str, Any]
    ) -> None:
        """Делится треком в публичном канале"""
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