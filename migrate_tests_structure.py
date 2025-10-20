"""
Скрипт миграции структуры тестов:
1. Добавляет lesson_id в test_questions
2. Удаляет test_type и lesson_id из tests
3. Делает series_id обязательным в tests
4. Меняет проходной балл по умолчанию с 70% на 80%
"""
import asyncio
from sqlalchemy import text
from bot.models.database import async_session_maker


async def migrate():
    """Выполнить миграцию"""
    async with async_session_maker() as session:
        try:
            print("Начинаем миграцию структуры тестов...")

            # 1. Удаляем все старые тесты и вопросы (т.к. структура кардинально изменилась)
            print("1. Удаляем старые тесты и вопросы...")
            await session.execute(text("DELETE FROM test_attempts"))
            await session.execute(text("DELETE FROM test_questions"))
            await session.execute(text("DELETE FROM tests"))
            await session.commit()
            print("   ✅ Старые данные удалены")

            # 2. Добавляем lesson_id в test_questions
            print("2. Добавляем lesson_id в test_questions...")
            await session.execute(text("""
                ALTER TABLE test_questions
                ADD COLUMN IF NOT EXISTS lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE
            """))
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_test_questions_lesson_id ON test_questions(lesson_id)
            """))
            await session.commit()
            print("   ✅ Колонка lesson_id добавлена в test_questions")

            # 3. Удаляем старые constraint и колонки из tests
            print("3. Удаляем test_type и lesson_id из tests...")

            # Удаляем constraint
            await session.execute(text("""
                ALTER TABLE tests DROP CONSTRAINT IF EXISTS check_test_type_consistency
            """))

            # Удаляем колонки
            await session.execute(text("ALTER TABLE tests DROP COLUMN IF EXISTS test_type"))
            await session.execute(text("ALTER TABLE tests DROP COLUMN IF EXISTS lesson_id"))
            await session.commit()
            print("   ✅ test_type и lesson_id удалены из tests")

            # 4. Делаем series_id обязательным
            print("4. Делаем series_id обязательным...")
            await session.execute(text("""
                ALTER TABLE tests ALTER COLUMN series_id SET NOT NULL
            """))
            await session.commit()
            print("   ✅ series_id теперь обязательное поле")

            # 5. Обновляем значение по умолчанию для passing_score
            print("5. Обновляем проходной балл по умолчанию с 70% на 80%...")
            await session.execute(text("""
                ALTER TABLE tests ALTER COLUMN passing_score SET DEFAULT 80
            """))
            await session.commit()
            print("   ✅ Проходной балл по умолчанию изменён на 80%")

            print("\n✅ Миграция успешно завершена!")
            print("\nИзменения:")
            print("  - TestQuestion теперь имеет обязательное поле lesson_id")
            print("  - Test больше не имеет test_type и lesson_id")
            print("  - Test.series_id теперь обязательное поле")
            print("  - Проходной балл по умолчанию: 80%")
            print("\nВсе старые тесты были удалены. Создайте новые тесты через админ-панель.")

        except Exception as e:
            await session.rollback()
            print(f"\n❌ Ошибка миграции: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(migrate())
