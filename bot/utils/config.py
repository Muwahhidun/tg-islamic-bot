"""
Конфигурация приложения
"""
import os
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Класс для управления настройками приложения"""
    
    # Telegram Bot Token
    bot_token: str = Field(..., env="BOT_TOKEN")
    
    # Database Configuration
    db_host: str = Field("localhost", env="DB_HOST")
    db_port: int = Field(5432, env="DB_PORT")
    db_name: str = Field("audio_bot", env="DB_NAME")
    db_user: str = Field("postgres", env="DB_USER")
    db_password: str = Field(..., env="DB_PASSWORD")
    
    @property
    def database_url(self) -> str:
        """Формирование URL для подключения к базе данных"""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    # Admin Configuration
    admin_telegram_id: int = Field(..., env="ADMIN_TELEGRAM_ID")
    
    def __post_init__(self):
        """Дополнительная инициализация после создания объекта"""
        # Убедимся, что admin_telegram_id является целым числом
        if isinstance(self.admin_telegram_id, str):
            self.admin_telegram_id = int(self.admin_telegram_id)
    
    # Application Configuration
    debug: bool = Field(False, env="DEBUG")
    log_level: str = Field("INFO", env="LOG_LEVEL")
    
    # File Configuration
    max_audio_size_mb: int = Field(50, env="MAX_AUDIO_SIZE_MB")
    allowed_audio_formats: str = Field("mp3,wav,ogg,m4a", env="ALLOWED_AUDIO_FORMATS")
    
    @property
    def allowed_audio_formats_list(self) -> List[str]:
        """Получение списка разрешенных аудиоформатов"""
        return [format.strip() for format in self.allowed_audio_formats.split(",")]
    
    @property
    def max_audio_size_bytes(self) -> int:
        """Получение максимального размера аудиофайла в байтах"""
        return self.max_audio_size_mb * 1024 * 1024
    
    # Paths
    audio_files_path: str = "bot/audio_files"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Создание экземпляра настроек
config = Settings()