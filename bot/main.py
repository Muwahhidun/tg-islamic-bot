"""
Основной файл запуска бота
"""
import asyncio
import logging
import os
import sys
import locale
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from bot.utils.config import config
from bot.handlers import user, admin
from bot.models.database import engine, Base
from bot.utils.timezone_utils import MOSCOW_TZ, get_moscow_now


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


async def init_roles():
    """
    Инициализация базовых ролей в базе данных
    """
    from bot.models import Role, async_session_maker
    from sqlalchemy import select

    async with async_session_maker() as session:
        # Проверяем, есть ли роли
        result = await session.execute(select(Role))
        existing_roles = result.scalars().all()

        if not existing_roles:
            # Создаем базовые роли
            roles = [
                Role(id=1, name="admin", description="Администратор"),
                Role(id=2, name="moderator", description="Модератор"),
                Role(id=3, name="user", description="Пользователь"),
            ]
            session.add_all(roles)
            await session.commit()
            logger.info("Базовые роли созданы")


async def check_system_encoding():
    """
    Проверка кодировок, локали и временной зоны
    """
    logger.info("=" * 60)
    logger.info("ПРОВЕРКА СИСТЕМНЫХ НАСТРОЕК")
    logger.info("=" * 60)

    # Проверка кодировки Python
    default_encoding = sys.getdefaultencoding()
    logger.info(f"Python default encoding: {default_encoding}")
    if default_encoding.lower() != 'utf-8':
        logger.warning(f"⚠️  Кодировка не UTF-8! Текущая: {default_encoding}")
    else:
        logger.info("✅ Кодировка UTF-8")

    # Проверка локали системы
    try:
        system_locale = locale.getlocale()
        logger.info(f"System locale: {system_locale}")
        if system_locale[0] and 'ru' in system_locale[0].lower():
            logger.info("✅ Русская локаль настроена")
        else:
            logger.warning(f"⚠️  Русская локаль не настроена: {system_locale}")
    except Exception as e:
        logger.warning(f"⚠️  Не удалось получить локаль: {e}")

    # Проверка временной зоны
    moscow_time_aware = datetime.now(MOSCOW_TZ)
    moscow_time_naive = get_moscow_now()
    timezone_str = moscow_time_aware.strftime('%Z %z')
    logger.info(f"Timezone: {timezone_str}")
    logger.info(f"Current Moscow time: {moscow_time_naive.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Time for DB (naive): {moscow_time_naive}")

    if '+03' in timezone_str or 'MSK' in timezone_str:
        logger.info("✅ Московское время (UTC+3)")
    else:
        logger.warning(f"⚠️  Время не соответствует Москве: {timezone_str}")

    # Тест кириллицы
    test_message = "Тест кириллицы: ✅ Кириллица работает корректно!"
    logger.info(test_message)

    logger.info("=" * 60)


async def main():
    """
    Основная функция запуска бота
    """
    # Проверка системных настроек
    await check_system_encoding()

    # Создание таблиц
    await create_tables()

    # Инициализация базовых ролей
    await init_roles()
    
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