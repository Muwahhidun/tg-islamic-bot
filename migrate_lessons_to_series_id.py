"""
Миграция уроков: проставляем series_id на основе series_year и series_name
"""
import asyncio
from sqlalchemy import select, and_
from bot.models.database import async_session_maker
from bot.models.lesson import Lesson
from bot.models.lesson_series import LessonSeries

async def migrate_lessons_to_series_id():
    """Обновить уроки без series_id - найти соответствующую серию и проставить series_id"""
    async with async_session_maker() as session:
        # Получаем все уроки без series_id
        result = await session.execute(
            select(Lesson).where(Lesson.series_id == None)
        )
        lessons_without_series_id = result.scalars().all()

        print(f"Найдено уроков без series_id: {len(lessons_without_series_id)}")

        updated_count = 0
        not_found_count = 0

        for lesson in lessons_without_series_id:
            # Ищем серию по year, name и teacher_id
            series_result = await session.execute(
                select(LessonSeries).where(
                    and_(
                        LessonSeries.year == lesson.series_year,
                        LessonSeries.name == lesson.series_name,
                        LessonSeries.teacher_id == lesson.teacher_id
                    )
                )
            )
            series = series_result.scalar_one_or_none()

            if series:
                lesson.series_id = series.id
                print(f"✅ Урок '{lesson.title}' → Серия '{series.year} - {series.name}' (ID: {series.id})")
                updated_count += 1
            else:
                print(f"❌ Серия не найдена для урока '{lesson.title}' ({lesson.series_year} - {lesson.series_name}, teacher_id={lesson.teacher_id})")
                not_found_count += 1

        await session.commit()

        print(f"\n{'='*60}")
        print(f"Обновлено уроков: {updated_count}")
        print(f"Серия не найдена: {not_found_count}")
        print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(migrate_lessons_to_series_id())
