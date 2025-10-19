"""
Основной файл запуска бота
"""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from bot.utils.config import config
from bot.handlers import user, admin
from bot.models.database import engine, Base


# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def create_tables():
    """
    Создание таблиц в базе данных
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Таблицы базы данных созданы")


async def main():
    """
    Основная функция запуска бота
    """
    # Создание таблиц
    await create_tables()
    
    # Создание бота
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )
    
    # Создание диспетчера
    dp = Dispatcher()
    
    # Включение роутеров
    dp.include_router(user.router)
    dp.include_router(admin.router)

    # Создание директории для аудиофайлов
    os.makedirs(config.audio_files_path, exist_ok=True)
    
    logger.info("Бот запускается...")
    
    # Удаление вебхуков и запуск поллинга
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")