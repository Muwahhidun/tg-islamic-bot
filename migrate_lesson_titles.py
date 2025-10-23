"""
Скрипт для обновления названий всех уроков на автоматически сгенерированные
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from bot.models.database import async_session_maker
from bot.models.lesson import Lesson


def generate_lesson_title(teacher_name: str, book_name: str, series_year: int, series_name: str, lesson_number: int) -> str:
    """Генерирует название урока из метаданных"""
    parts = []
    if teacher_name:
        parts.append(teacher_name.replace(" ", "_"))
    if book_name:
        parts.append(book_name.replace(" ", "_"))
    parts.append(str(series_year))
    parts.append(series_name.replace(" ", "_"))
    parts.append(f"урок_{lesson_number}")
    return "_".join(parts)


async def migrate_lesson_titles():
    """Обновляет названия всех уроков"""
    async with async_session_maker() as session:
        # Загружаем все уроки с relationships
        result = await session.execute(
            select(Lesson)
            .options(
                joinedload(Lesson.series),
                joinedload(Lesson.teacher),
                joinedload(Lesson.book)
            )
        )
        lessons = result.scalars().unique().all()

        print(f"\nНайдено уроков: {len(lessons)}\n")
        print("=" * 80)

        updated_count = 0
        skipped_count = 0

        for lesson in lessons:
            # Проверяем наличие необходимых данных
            if not lesson.series:
                print(f"⚠️  Урок {lesson.id}: пропущен (нет series)")
                skipped_count += 1
                continue

            # Генерируем новое название
            new_title = generate_lesson_title(
                teacher_name=lesson.teacher.name if lesson.teacher else "",
                book_name=lesson.book.name if lesson.book else "",
                series_year=lesson.series.year,
                series_name=lesson.series.name,
                lesson_number=lesson.lesson_number if lesson.lesson_number else 0
            )

            # Обновляем только если название изменилось
            if lesson.title != new_title:
                old_title = lesson.title
                lesson.title = new_title
                # Сбрасываем file_id чтобы при следующей отправке использовалось новое название
                lesson.telegram_file_id = None

                print(f"✅ Урок {lesson.id}:")
                print(f"   Старое: {old_title}")
                print(f"   Новое:  {new_title}")
                print()

                updated_count += 1
            else:
                print(f"⏭️  Урок {lesson.id}: уже актуальное название")
                skipped_count += 1

        # Сохраняем изменения
        await session.commit()

        print("=" * 80)
        print(f"\n✅ Обновлено уроков: {updated_count}")
        print(f"⏭️  Пропущено (без изменений): {skipped_count}")
        print(f"📊 Всего обработано: {len(lessons)}\n")


if __name__ == "__main__":
    print("\n🔄 Миграция названий уроков на автоматически сгенерированные\n")
    asyncio.run(migrate_lesson_titles())
    print("✅ Миграция завершена!\n")
