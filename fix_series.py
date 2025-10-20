import asyncio
from sqlalchemy import select, and_
from bot.models.database import async_session_maker
from bot.models.lesson import Lesson
from bot.models.lesson_series import LessonSeries

async def fix():
    async with async_session_maker() as session:
        result = await session.execute(select(Lesson).where(Lesson.series_id == None))
        lessons = result.scalars().all()
        print(f'Найдено: {len(lessons)}')
        updated = 0
        for lesson in lessons:
            sr = await session.execute(select(LessonSeries).where(and_(LessonSeries.year == lesson.series_year, LessonSeries.name == lesson.series_name, LessonSeries.teacher_id == lesson.teacher_id)))
            series = sr.scalar_one_or_none()
            if series:
                lesson.series_id = series.id
                updated += 1
        await session.commit()
        print(f'Обновлено: {updated}')
asyncio.run(fix())
