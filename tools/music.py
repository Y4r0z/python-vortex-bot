import os
import re
import json
import soundfile as sf
import librosa
import numpy as np
import yt_dlp
import asyncio
import aiohttp
import discord
from pedalboard import Pedalboard, Limiter, Gain
from pathlib import Path
from math import log10
from typing import Optional, Dict, Any, List, Tuple, TypedDict
from datetime import datetime
from urllib.parse import quote
from transliterate import translit
from ytmusicapi import YTMusic
from html import unescape

import settings
from lib.vortex_api import GetPlayerTrack, PlayerMusic

logger = settings.logging.getLogger("discord")


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
    def extract_youtube_id(url: str) -> Optional[str]:
        patterns = [
            r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|v\/|embed\/|shorts\/|live\/)?([a-zA-Z0-9_-]{11})(?:&|\?|#|$)',
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/attribution_link\?.*?u=%2Fwatch%3Fv%3D([a-zA-Z0-9_-]{11})',
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/user\/[^\/]+\#p\/[^\/]+\/\d+\/([a-zA-Z0-9_-]{11})',
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/\?v=([a-zA-Z0-9_-]{11})',
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/\?vi=([a-zA-Z0-9_-]{11})',
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/(?:(?!v=).)*&v=([a-zA-Z0-9_-]{11})',
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?vi=([a-zA-Z0-9_-]{11})',
            r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/vi\/([a-zA-Z0-9_-]{11})',
            r'(?:https?:\/\/)?(?:www\.)?youtube-nocookie\.com\/(?:v|embed)\/([a-zA-Z0-9_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    @staticmethod
    def is_youtube_url(url: str) -> bool:
        return TrackUtils.extract_youtube_id(url) is not None

    @staticmethod
    def get_platform_links(query: str) -> List[str]:
        return [platform.get_link_markdown(query) for platform in TrackUtils.MUSIC_PLATFORMS.values()]
    
    @staticmethod
    def create_track_embed(
        title: str,
        track_name: str,
        thumbnail_url: str = None,
        color: discord.Color = discord.Color.from_rgb(88, 101, 242),
        **kwargs
    ) -> discord.Embed:
        embed = discord.Embed(title=title, color=color)
        embed.description = f"**{track_name}**"
        
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
            
        for name, value in kwargs.items():
            if value:
                embed.add_field(name=name, value=value, inline=False)
                
        return embed
    
    @staticmethod
    async def get_youtube_thumbnail(url: str) -> Optional[str]:
        try:
            video_id = TrackUtils.extract_youtube_id(url)
            if video_id:
                ytmusic = YTMusic()
                try:
                    track_info = ytmusic.get_song(video_id)
                    if track_info and 'videoDetails' in track_info:
                        return track_info['videoDetails']['thumbnail']['thumbnails'][-1]['url']
                except Exception as e:
                    logger.error(f'Error getting track thumbnail for ID {video_id}: {str(e)}')
        except Exception as e:
            logger.error(f'Error getting track thumbnail: {str(e)}')
        return None
    
    @staticmethod
    def clean_track_name(title: str) -> str:
        import re
        
        brackets_pattern = r'\s*[\(\[\{].*?[\)\]\}]'
        cleaned = re.sub(brackets_pattern, '', title)
        
        if ' - ' in cleaned:
            song_part, artists_part = cleaned.split(' - ', 1)
            first_artist = artists_part.split(',')[0].strip()
            cleaned = f"{song_part.strip()} - {first_artist}"
        
        cleaned = ' '.join(cleaned.split())
        
        return cleaned


class NextSeasonTrackManager:
    def __init__(self):
        self.tracks_file = 'preferences/tracks.json'
        
    async def can_set_track(self) -> bool:
        now = datetime.utcnow()
        return 0 <= now.day
        
    async def get_next_season_track(self, steam_id: str) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self.tracks_file):
            return None
            
        try:
            with open(self.tracks_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get(steam_id)
        except (json.JSONDecodeError, FileNotFoundError):
            return None
            
    async def set_next_season_track(self, steam_id: str, track_data: Dict[str, Any]) -> bool:
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
        try:
            return await GetPlayerTrack(steam_id)
        except Exception as e:
            logger.error(f"Error getting current track: {str(e)}")
            return None


class MusicConverter:
    def __init__(self):
        self.conversion_queue = asyncio.Queue()
        self.processing = False
        self.base_path = Path("/app")
        self.temp_folder = self.base_path / "temp"
        self.output_folder = Path("/var/www/html/fastdl/sound/ui")
        self.tracks_file = self.base_path / "preferences" / "tracks.json"
        
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.temp_folder.mkdir(parents=True, exist_ok=True)
        
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': str(self.temp_folder / '%(title)s.%(ext)s'),
            'quiet': True,
        }

        self.background_task = None

    def start_processing(self, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        if self.background_task is None or self.background_task.done():
            self.background_task = loop.create_task(self.process_queue())
            
    def stop_processing(self):
        if self.background_task:
            self.background_task.cancel()

    def clean_filename(self, title: str) -> str:
        transliterated = translit(title, 'ru', reversed=True)
        safe_name = re.sub(r'[^a-zA-Z0-9]', '', transliterated.lower())
        safe_name = safe_name[:15]
        return f"{safe_name}.mp3"
    
    async def save_track_data(self, steam_id: str, track_data: dict) -> bool:
        try:
            self.tracks_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {}
            if self.tracks_file.exists():
                with open(self.tracks_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        data = json.loads(content)

            data[steam_id] = track_data

            with open(self.tracks_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            logger.info(f"Successfully saved track data for {steam_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving track data: {str(e)}")
            return False

    async def process_queue(self):
        while True:
            try:
                if not self.processing:
                    task = await self.conversion_queue.get()
                    self.processing = True
                    
                    steam_id, url, title = task
                    success, file_path = await self.process_track(url, title)
                    
                    if success:
                        logger.info(f"Successfully converted track for {steam_id}: {title}")
                        await self.update_track_path(steam_id, file_path)
                    else:
                        logger.error(f"Failed to convert track for {steam_id}: {title}")
                    
                    self.processing = False
                    self.conversion_queue.task_done()
                else:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in conversion queue: {str(e)}")
                self.processing = False
                await asyncio.sleep(1)

    async def process_track(self, url: str, title: str) -> tuple[bool, str]:
        try:
            if not url or not title:
                return False, "Invalid input"
            
            if not self.output_folder.exists():
                logger.info(f"Creating output folder: {self.output_folder}")
                self.output_folder.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Checking permissions for folder: {self.output_folder}")
            if not os.access(str(self.output_folder), os.W_OK):
                logger.error(f"No write permission to output folder: {self.output_folder}")
                logger.debug(f"Folder permissions: {oct(os.stat(str(self.output_folder)).st_mode)}")
                logger.debug(f"Current user/group: {os.getuid()}:{os.getgid()}")
                return False, "Permission denied"
        
            output_filename = self.clean_filename(title)
            output_path = self.output_folder / output_filename
        
            logger.info(f"Testing file creation: {output_path}")
            try:
                with open(output_path, 'a'): pass
                os.unlink(output_path)
                logger.info("File creation test successful")
            except IOError as e:
                logger.error(f"Cannot write to output file {output_path}: {e}")
                logger.debug(f"Parent folder permissions: {oct(os.stat(str(output_path.parent)).st_mode)}")
                return False, f"Permission denied: {str(e)}"
        
            downloaded_file = await self.download_track(url)
        
            if not downloaded_file:
                return False, ""
            
            MAX_FILE_SIZE = 50 * 1024 * 1024
            if os.path.getsize(str(downloaded_file)) > MAX_FILE_SIZE:
                downloaded_file.unlink(missing_ok=True)
                return False, "File too large"

            await self.process_audio(str(downloaded_file), str(output_path))
        
            downloaded_file.unlink(missing_ok=True)
            return True, f"ui/{output_filename}"
            
        except Exception as e:
            logger.error(f"Error processing track {url}: {str(e)}")
            return False, str(e)

    async def download_track(self, url: str) -> Optional[Path]:
        try:
            video_id = TrackUtils.extract_youtube_id(url)
            if video_id:
                normalized_url = f"https://www.youtube.com/watch?v={video_id}"
                logger.info(f"Normalized YouTube URL: {url} -> {normalized_url}")
                url = normalized_url
            
            def _download():
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    return Path(filename).with_suffix('.mp3')
            
            return await asyncio.to_thread(_download)
        except Exception as e:
            logger.error(f"Error downloading track {url}: {str(e)}")
            return None

    async def process_audio(self, input_file: str, output_file: str):
        def _process():
            audio, original_sr = sf.read(input_file)
            
            board = Pedalboard([
                Gain(gain_db=8.0),
                Limiter(
                    threshold_db=-0.5,
                    release_ms=100.0
                ),
                Gain(gain_db=2.0)
            ])
            
            effected = board(audio, original_sr)
            
            if original_sr != 44100:
                if len(effected.shape) > 1:
                    resampled_left = librosa.resample(
                        y=effected[:, 0],
                        orig_sr=original_sr,
                        target_sr=44100
                    )
                    resampled_right = librosa.resample(
                        y=effected[:, 1],
                        orig_sr=original_sr,
                        target_sr=44100
                    )
                    resampled = np.vstack((resampled_left, resampled_right)).T
                else:
                    resampled = librosa.resample(
                        y=effected,
                        orig_sr=original_sr,
                        target_sr=44100
                    )
            else:
                resampled = effected
            
            temp_output = output_file + ".temp.wav"
            sf.write(temp_output, resampled, 44100)
            
            import subprocess
            try:
                subprocess.run([
                    'ffmpeg', 
                    '-y',
                    '-i', temp_output, 
                    '-b:a', '120k',
                    '-codec:a', 'libmp3lame',
                    output_file
                ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg конвертация не удалась: {e.stderr.decode() if e.stderr else str(e)}")
                sf.write(output_file, resampled, 44100)
            finally:
                if os.path.exists(temp_output):
                    os.unlink(temp_output)
        
        await asyncio.to_thread(_process)

    async def update_track_path(self, steam_id: str, path: str) -> bool:
        try:
            if self.tracks_file.exists():
                with open(self.tracks_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if steam_id in data:
                    data[steam_id]['path'] = path
                    with open(self.tracks_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Error updating track path: {str(e)}")
            return False

    async def add_to_queue(self, steam_id: str, url: str, title: str) -> bool:
        try:
            await self.conversion_queue.put((steam_id, url, title))
            return True
        except Exception as e:
            logger.error(f"Error adding track to queue: {str(e)}")
            return False


async def get_track_info_from_url(url: str) -> Optional[Tuple[str, str]]:
    try:
        video_id = TrackUtils.extract_youtube_id(url)
        if video_id:
            try:
                ytmusic = YTMusic()
                track_info = ytmusic.get_song(video_id)
                if track_info and 'videoDetails' in track_info:
                    def clean_search_text(text: str) -> str:
                        text = unescape(text)
                        
                        if " on " in text:
                            text = text.split(" on ")[0]
                        
                        if text.endswith(")"):
                            base = text[:-1]
                            if " by " in base:
                                text = base.split(" by ")[0] + ")"
                        else:
                            if " by " in text:
                                text = text.split(" by ")[0]
                        
                        return text.strip()
                    
                    title = clean_search_text(track_info['videoDetails']['title'])
                    artist = clean_search_text(track_info['videoDetails']['author'])
                    return title, artist
            except Exception as e:
                logger.error(f'Error getting track info from YouTube API for ID {video_id}: {str(e)}')
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
            }
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return None
                
                html_content = await response.text()
                
                def clean_search_text(text: str) -> str:
                    text = unescape(text)
                    
                    if " on " in text:
                        text = text.split(" on ")[0]
                    
                    if text.endswith(")"):
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
                    title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
                    artist_match = re.search(r'<meta property="og:description" content="([^"]+)"', html_content)
                    
                    if title_match and artist_match:
                        title = clean_search_text(title_match.group(1))
                        artist = clean_search_text(artist_match.group(1).split('·')[0])
                        return title, artist

                elif 'music.yandex' in url:
                    json_match = re.search(r'<script type="application/ld\+json">(.+?)</script>', html_content)
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

                    title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
                    if title_match:
                        title = clean_search_text(title_match.group(1))
                        if ' - ' in title:
                            artist, track = title.split(' - ', 1)
                            return clean_search_text(track), clean_search_text(artist)

                elif 'music.apple.com' in url:
                    json_match = re.search(r'<script type="application/ld\+json">(.+?)</script>', html_content)
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
                    
                    title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
                    desc_match = re.search(r'<meta property="og:description" content="([^"]+)"', html_content)
                    
                    if title_match and desc_match:
                        title = clean_search_text(title_match.group(1))
                        description = clean_search_text(desc_match.group(1))
                        artist_match = re.search(r'Song · (.+?) ·', description)
                        if artist_match:
                            artist = clean_search_text(artist_match.group(1))
                            return title, artist
                
                title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
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

def load_role_ids():
    try:
        with open('preferences/ids.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f'Error loading role IDs: {str(e)}')
        return {}

music_converter = MusicConverter()
track_manager = NextSeasonTrackManager()