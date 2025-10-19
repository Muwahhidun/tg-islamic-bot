"""
Миграция базы данных: добавление таблицы lesson_series
и миграция существующих данных из lessons

Этот скрипт:
1. Создаёт таблицу lesson_series
2. Добавляет поле series_id в таблицу lessons
3. Создаёт служебную серию "Без серии"
4. Мигрирует существующие уроки в серии
5. Делает поля series_year и series_name nullable (для удаления позже)
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.append(str(Path(__file__).parent))

from sqlalchemy import select, text, and_
from sqlalchemy.ext.asyncio import create_async_engine
from bot.models.database import async_session_maker, Base
from bot.models import LessonSeries, Lesson, LessonTeacher
from bot.utils.timezone_utils import get_moscow_now


async def run_migration():
    """Запуск миграции"""

    print("=" * 60)
    print("МИГРАЦИЯ: Добавление lesson_series")
    print("=" * 60)
    print()

    async with async_session_maker() as session:
        try:
            # Шаг 1: Создаём таблицу lesson_series через SQLAlchemy
            print("Шаг 1: Создание таблицы lesson_series...")
            from bot.models.database import engine
            async with engine.begin() as conn:
                # Создаём только таблицу lesson_series
                await conn.run_sync(lambda sync_conn: LessonSeries.__table__.create(sync_conn, checkfirst=True))
            print("✅ Таблица lesson_series создана")
            print()

            # Шаг 2: Добавляем поле series_id в lessons (если его нет)
            print("Шаг 2: Добавление поля series_id в таблицу lessons...")
            try:
                await session.execute(text("""
                    ALTER TABLE lessons
                    ADD COLUMN IF NOT EXISTS series_id INTEGER REFERENCES lesson_series(id) ON DELETE SET NULL
                """))
                await session.execute(text("CREATE INDEX IF NOT EXISTS ix_lessons_series_id ON lessons(series_id)"))
                await session.commit()
                print("✅ Поле series_id добавлено")
            except Exception as e:
                print(f"⚠️  Поле series_id возможно уже существует: {e}")
                await session.rollback()
            print()

            # Шаг 3: Делаем series_year и series_name nullable
            print("Шаг 3: Изменение полей series_year и series_name на nullable...")
            try:
                await session.execute(text("ALTER TABLE lessons ALTER COLUMN series_year DROP NOT NULL"))
                await session.execute(text("ALTER TABLE lessons ALTER COLUMN series_name DROP NOT NULL"))
                await session.commit()
                print("✅ Поля series_year и series_name теперь nullable")
            except Exception as e:
                print(f"⚠️  Возможно поля уже nullable: {e}")
                await session.rollback()
            print()

            # Шаг 4: Получаем первого преподавателя для служебной серии
            print("Шаг 4: Поиск преподавателя для служебной серии...")
            result = await session.execute(select(LessonTeacher).where(LessonTeacher.is_active == True).limit(1))
            default_teacher = result.scalar_one_or_none()

            if not default_teacher:
                print("❌ ОШИБКА: Не найдено ни одного преподавателя!")
                print("Сначала создайте хотя бы одного преподавателя")
                return

            print(f"✅ Используем преподавателя: {default_teacher.name} (ID: {default_teacher.id})")
            print()

            # Шаг 5: Создаём служебную серию "Без серии"
            print("Шаг 5: Создание служебной серии 'Без серии'...")
            result = await session.execute(
                select(LessonSeries).where(
                    and_(
                        LessonSeries.year == 1900,
                        LessonSeries.name == "Без серии"
                    )
                )
            )
            default_series = result.scalar_one_or_none()

            if not default_series:
                default_series = LessonSeries(
                    name="Без серии",
                    year=1900,
                    description="Служебная серия для уроков без серии",
                    teacher_id=default_teacher.id,
                    is_completed=False,
                    order=-1,  # Показывать последней
                    is_active=True
                )
                session.add(default_series)
                await session.commit()
                await session.refresh(default_series)
                print(f"✅ Создана служебная серия 'Без серии' (ID: {default_series.id})")
            else:
                print(f"✅ Служебная серия уже существует (ID: {default_series.id})")
            print()

            # Шаг 6: Получаем все уникальные комбинации (year, name, teacher_id) из уроков
            print("Шаг 6: Анализ существующих уроков...")
            result = await session.execute(
                select(
                    Lesson.series_year,
                    Lesson.series_name,
                    Lesson.teacher_id,
                    Lesson.book_id,
                    Lesson.theme_id
                ).distinct()
            )
            unique_series = result.all()
            print(f"✅ Найдено {len(unique_series)} уникальных серий")
            print()

            # Шаг 7: Создаём серии для каждой уникальной комбинации
            print("Шаг 7: Создание серий из существующих уроков...")
            created_series_count = 0
            series_mapping = {}  # (year, name, teacher_id) -> series_id

            for series_year, series_name, teacher_id, book_id, theme_id in unique_series:
                # Пропускаем если нет года или имени
                if not series_year or not series_name:
                    continue

                # Если нет преподавателя, используем дефолтного
                if not teacher_id:
                    teacher_id = default_teacher.id

                # Проверяем, не существует ли уже такая серия
                result = await session.execute(
                    select(LessonSeries).where(
                        and_(
                            LessonSeries.year == series_year,
                            LessonSeries.name == series_name,
                            LessonSeries.teacher_id == teacher_id
                        )
                    )
                )
                existing_series = result.scalar_one_or_none()

                if existing_series:
                    series_mapping[(series_year, series_name, teacher_id)] = existing_series.id
                    continue

                # Создаём новую серию
                new_series = LessonSeries(
                    name=series_name,
                    year=series_year,
                    teacher_id=teacher_id,
                    book_id=book_id,
                    theme_id=theme_id,
                    is_completed=False,
                    is_active=True
                )
                session.add(new_series)
                await session.flush()  # Получаем ID

                series_mapping[(series_year, series_name, teacher_id)] = new_series.id
                created_series_count += 1
                print(f"  ✅ Создана серия: {series_year} - {series_name} (ID: {new_series.id})")

            await session.commit()
            print(f"\n✅ Создано {created_series_count} новых серий")
            print()

            # Шаг 8: Обновляем series_id в уроках
            print("Шаг 8: Привязка уроков к сериям...")
            result = await session.execute(select(Lesson))
            lessons = result.scalars().all()

            updated_count = 0
            for lesson in lessons:
                if lesson.series_id:
                    # Уже привязан
                    continue

                if lesson.series_year and lesson.series_name and lesson.teacher_id:
                    # Ищем соответствующую серию
                    key = (lesson.series_year, lesson.series_name, lesson.teacher_id)
                    if key in series_mapping:
                        lesson.series_id = series_mapping[key]
                        updated_count += 1
                else:
                    # Привязываем к служебной серии
                    lesson.series_id = default_series.id
                    updated_count += 1

            await session.commit()
            print(f"✅ Обновлено {updated_count} уроков")
            print()

            # Статистика
            print("=" * 60)
            print("МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
            print("=" * 60)
            print()
            print(f"📊 Статистика:")
            print(f"  • Создано серий: {created_series_count + 1} (+1 служебная)")
            print(f"  • Обновлено уроков: {updated_count}")
            print()
            print("⚠️  ВАЖНО: Старые поля series_year и series_name оставлены для совместимости")
            print("   Их можно будет удалить после проверки что всё работает корректно")
            print()
            print("🔄 Следующие шаги:")
            print("   1. Перезапустить бота: docker-compose restart bot")
            print("   2. Проверить что уроки отображаются корректно")
            print("   3. При необходимости удалить старые поля: series_year, series_name")
            print()

        except Exception as e:
            print(f"\n❌ ОШИБКА МИГРАЦИИ: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
            raise


if __name__ == "__main__":
    print("\n⚠️  ВНИМАНИЕ: Это изменит структуру базы данных!")
    print("   Убедитесь что у вас есть бэкап!\n")

    response = input("Продолжить миграцию? (yes/no): ")
    if response.lower() != "yes":
        print("Миграция отменена")
        sys.exit(0)

    print("\n🚀 Запуск миграции...\n")
    asyncio.run(run_migration())
