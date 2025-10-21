#!/usr/bin/env python3
"""
Миграция: добавление поля telegram_file_id в таблицу lessons
для кеширования Telegram file_id и ускорения отправки аудио
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from bot.models.database import async_session


async def add_telegram_file_id_column():
    """Добавляет поле telegram_file_id в таблицу lessons"""

    async with async_session() as session:
        async with session.begin():
            # Проверяем, существует ли уже колонка
            result = await session.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='lessons'
                AND column_name='telegram_file_id'
            """))

            if result.fetchone():
                print("✅ Колонка telegram_file_id уже существует")
                return

            # Добавляем колонку
            await session.execute(text("""
                ALTER TABLE lessons
                ADD COLUMN telegram_file_id VARCHAR(200)
            """))

            print("✅ Колонка telegram_file_id успешно добавлена")
            print("ℹ️  Теперь аудиофайлы будут кешироваться для быстрой отправки")


async def main():
    """Основная функция миграции"""
    print("=" * 60)
    print("Миграция: добавление telegram_file_id в lessons")
    print("=" * 60)

    try:
        await add_telegram_file_id_column()
        print("\n✅ Миграция завершена успешно!")

    except Exception as e:
        print(f"\n❌ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
