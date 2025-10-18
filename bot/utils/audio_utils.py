"""
Утилиты для работы с аудиофайлами
"""
import os
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4

from bot.utils.config import config


class AudioUtils:
    """Утилиты для работы с аудиофайлами"""
    
    @staticmethod
    def get_audio_duration(file_path: str) -> Optional[int]:
        """
        Получение длительности аудиофайла в секундах
        
        Args:
            file_path: Путь к аудиофайлу
            
        Returns:
            Длительность в секундах или None в случае ошибки
        """
        try:
            audio_file = MutagenFile(file_path)
            if audio_file is not None:
                return int(audio_file.info.length)
        except Exception as e:
            print(f"Ошибка при получении длительности аудио: {e}")
        return None
    
    @staticmethod
    def validate_audio_file(file_path: str) -> bool:
        """
        Проверка валидности аудиофайла
        
        Args:
            file_path: Путь к аудиофайлу
            
        Returns:
            True если файл валидный, иначе False
        """
        try:
            audio_file = MutagenFile(file_path)
            return audio_file is not None
        except Exception:
            return False
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """
        Получение расширения файла
        
        Args:
            filename: Имя файла
            
        Returns:
            Расширение файла в нижнем регистре
        """
        return Path(filename).suffix.lower()
    
    @staticmethod
    def is_audio_file(filename: str) -> bool:
        """
        Проверка, является ли файл аудиофайлом поддерживаемого формата
        
        Args:
            filename: Имя файла
            
        Returns:
            True если файл поддерживаемого аудиоформата
        """
        extension = AudioUtils.get_file_extension(filename)
        return extension in [f".{fmt}" for fmt in config.allowed_audio_formats_list]
    
    @staticmethod
    def generate_unique_filename(original_filename: str) -> str:
        """
        Генерация уникального имени файла
        
        Args:
            original_filename: Оригинальное имя файла
            
        Returns:
            Уникальное имя файла с тем же расширением
        """
        extension = AudioUtils.get_file_extension(original_filename)
        unique_name = f"{uuid.uuid4()}{extension}"
        return unique_name
    
    @staticmethod
    def get_audio_file_path(filename: str) -> str:
        """
        Получение полного пути к аудиофайлу
        
        Args:
            filename: Имя файла
            
        Returns:
            Полный путь к файлу
        """
        return os.path.join(config.audio_files_path, filename)
    
    @staticmethod
    async def save_audio_file(file_content: bytes, filename: str) -> str:
        """
        Сохранение аудиофайла
        
        Args:
            file_content: Содержимое файла
            filename: Имя файла
            
        Returns:
            Путь к сохраненному файлу
        """
        # Создание директории, если она не существует
        os.makedirs(config.audio_files_path, exist_ok=True)
        
        # Генерация уникального имени файла
        unique_filename = AudioUtils.generate_unique_filename(filename)
        file_path = AudioUtils.get_audio_file_path(unique_filename)
        
        # Сохранение файла
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        return file_path
    
    @staticmethod
    def file_exists(file_path: str) -> bool:
        """
        Проверка существования файла
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если файл существует
        """
        return os.path.exists(file_path)
    
    @staticmethod
    def get_file_size(file_path: str) -> int:
        """
        Получение размера файла в байтах
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Размер файла в байтах
        """
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0
    
    @staticmethod
    def is_file_size_valid(file_path: str) -> bool:
        """
        Проверка, соответствует ли размер файла лимитам
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если размер файла в пределах лимита
        """
        file_size = AudioUtils.get_file_size(file_path)
        return file_size <= config.max_audio_size_bytes
    
    @staticmethod
    def format_duration(seconds: int) -> str:
        """
        Форматирование длительности в строку
        
        Args:
            seconds: Длительность в секундах
            
        Returns:
            Отформатированная строка длительности
        """
        if not seconds:
            return "00:00"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    @staticmethod
    def format_file_size(bytes_size: int) -> str:
        """
        Форматирование размера файла в человекочитаемый формат
        
        Args:
            bytes_size: Размер в байтах
            
        Returns:
            Отформатированная строка размера
        """
        if bytes_size == 0:
            return "0 Б"
        
        size_names = ["Б", "КБ", "МБ", "ГБ"]
        i = 0
        size = float(bytes_size)
        
        while size >= 1024.0 and i < len(size_names) - 1:
            size /= 1024.0
            i += 1
        
        return f"{size:.1f} {size_names[i]}"