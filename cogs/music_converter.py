import os
from pathlib import Path
from math import log10

import soundfile as sf
from pedalboard import Pedalboard, Limiter, Gain
import yt_dlp
import librosa
import numpy as np

import re
import json
import asyncio
import settings
from discord.ext import commands
from transliterate import translit

logger = settings.logging.getLogger("discord")

class MusicConverterCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.conversion_queue = asyncio.Queue()
        self.processing = False
        self.base_path = Path("/app")
        self.temp_folder = self.base_path / "temp"  # Используем общую temp папку
        self.output_folder = Path("/var/www/html/fastdl/sound/ui")
        self.tracks_file = self.base_path / "preferences" / "tracks.json"
        
        # Создаём необходимые директории
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        # Настройки для yt-dlp
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

        # Запускаем обработчик очереди
        self.background_task = self.bot.loop.create_task(self.process_queue())

    def clean_filename(self, title: str) -> str:
        """
        Преобразует название трека в безопасное имя файла:
        - Транслитерация кириллицы в латиницу
        - Ограничение длины до 15 символов
        - Удаление специальных символов
        """
        # Транслитерация кириллицы
        transliterated = translit(title, 'ru', reversed=True)
        
        # Удаляем все символы кроме букв и цифр
        safe_name = re.sub(r'[^a-zA-Z0-9]', '', transliterated.lower())
        
        # Ограничиваем длину до 15 символов
        safe_name = safe_name[:15]
        
        # Добавляем расширение
        return f"{safe_name}.mp3"
    
    async def save_track_data(self, steam_id: str, track_data: dict) -> bool:
        """Сохраняет данные трека в JSON файл"""
        try:
            # Создаем директорию если её нет
            self.tracks_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Загружаем существующие данные
            data = {}
            if self.tracks_file.exists():
                with open(self.tracks_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if content.strip():
                        data = json.loads(content)

            # Обновляем данные
            data[steam_id] = track_data

            # Сохраняем обновленные данные
            with open(self.tracks_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            logger.info(f"Successfully saved track data for {steam_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving track data: {str(e)}")
            return False

    async def process_queue(self):
        """Фоновый обработчик очереди конвертации"""
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
        """
        Обработка одного трека
        Returns: (success, path)
        """
        try:
            if not url or not title:
                return False, "Invalid input"
            # Проверка существования директорий
            if not self.output_folder.exists():
                logger.info(f"Creating output folder: {self.output_folder}")
                self.output_folder.mkdir(parents=True, exist_ok=True)
            # Проверяем права до создания файла
            logger.info(f"Checking permissions for folder: {self.output_folder}")
            if not os.access(str(self.output_folder), os.W_OK):
                logger.error(f"No write permission to output folder: {self.output_folder}")
                logger.debug(f"Folder permissions: {oct(os.stat(str(self.output_folder)).st_mode)}")
                logger.debug(f"Current user/group: {os.getuid()}:{os.getgid()}")
                return False, "Permission denied"
        
            # Формируем безопасное имя файла
            output_filename = self.clean_filename(title)
            output_path = self.output_folder / output_filename
        
            # Проверяем возможность записи файла
            logger.info(f"Testing file creation: {output_path}")
            try:
                with open(output_path, 'a'): pass
                os.unlink(output_path)
                logger.info("File creation test successful")
            except IOError as e:
                logger.error(f"Cannot write to output file {output_path}: {e}")
                logger.debug(f"Parent folder permissions: {oct(os.stat(str(output_path.parent)).st_mode)}")
                return False, f"Permission denied: {str(e)}"
        
            # Загружаем файл
            loop = asyncio.get_event_loop()
            downloaded_file = await loop.run_in_executor(
                None, self.download_track, url
            )
        
            if not downloaded_file:
                return False, ""
            # Проверка размера файла
            MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
            if os.path.getsize(str(downloaded_file)) > MAX_FILE_SIZE:
                downloaded_file.unlink(missing_ok=True)
                return False, "File too large"

            # Новая обработка аудио
            def process_audio(input_file, output_file):
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
                
                sf.write(output_file, resampled, 44100)

            # Вызываем новую функцию обработки
            process_audio(str(downloaded_file), str(output_path))
        
            # Удаляем временный файл
            downloaded_file.unlink(missing_ok=True)
        
            return True, f"ui/{output_filename}"
            
        except Exception as e:
            logger.error(f"Error processing track {url}: {str(e)}")
            return False, str(e)

    def download_track(self, url: str) -> Path:
        """Загрузка трека с YouTube Music"""
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return Path(filename).with_suffix('.mp3')
        except Exception as e:
            logger.error(f"Error downloading track {url}: {str(e)}")
            return None

    async def update_track_path(self, steam_id: str, path: str) -> bool:
        """Обновляет путь к файлу в JSON"""
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
        """Добавление трека в очередь на конвертацию"""
        try:
            await self.conversion_queue.put((steam_id, url, title))
            return True
        except Exception as e:
            logger.error(f"Error adding track to queue: {str(e)}")
            return False

    def cog_unload(self):
        """Очистка при выгрузке кога"""
        if self.background_task:
            self.background_task.cancel()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicConverterCog(bot))