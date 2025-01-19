import discord
import settings
from discord import app_commands
from discord.ext import commands
from ytmusicapi import YTMusic
import json
import os
import re
from urllib.parse import urlparse, quote
import requests
from tools.ds import tryGetOtherUser

logger = settings.logging.getLogger('discord')
EMBED_COLOR = discord.Color.from_rgb(88, 101, 242)  # Discord Blurple

async def get_track_info_from_url(url: str) -> tuple[str, str] | None:
    """
    Получает информацию о треке из URL любого поддерживаемого сервиса
    Returns: tuple(title, artist) или None
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        
        if 'music.youtube.com' in url:
            video_id = url.split('v=')[1].split('&')[0]
            ytmusic = YTMusic()
            track_info = ytmusic.get_song(video_id)
            if track_info and 'videoDetails' in track_info:
                return track_info['videoDetails']['title'], track_info['videoDetails']['author']
        
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
        self.add_platform_buttons()
        
    def add_platform_buttons(self):
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
        
        search_query = f"{self.track['title']} {self.track['artists'][0]['name']}"
        encoded_query = quote(search_query)
        
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
                f"[🎵 YouTube]({track_url})",
                f"[🟢 Spotify](https://open.spotify.com/search/{encoded_query})",
                f"[🎧 Yandex](https://music.yandex.ru/search?text={encoded_query})",
                f"[🍎 Apple](https://music.apple.com/search?term={encoded_query})"
            ]
            
            public_embed = discord.Embed(
                title="🎵 Новый любимый трек!",
                description=f"{interaction.user.mention} выбрал:\n**{track_title}**\n\n{' • '.join(links)}",
                color=EMBED_COLOR
            )
            public_embed.set_thumbnail(url=self.track['thumbnails'][0]['url'])
            
            await interaction.channel.send(embed=public_embed)
            
            logger.info(f'Added track to queue for user {steam_id} ({interaction.user.name}): {track_title}')
            
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
        super().__init__()

    @app_commands.command(
        name='mytrack',
        description='🎵 Установить любимый трек (поддерживает ссылки из разных сервисов)'
    )
    async def mytrack(self, interaction: discord.Interaction) -> None:
        logger.info(f'MyTrack command called by {interaction.user.id} ({interaction.user.name})')
        try:
            modal = TrackSearchModal(self.bot)
            await interaction.response.send_modal(modal)
            
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