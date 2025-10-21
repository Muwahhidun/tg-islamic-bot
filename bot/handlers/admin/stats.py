"""
Обработчик статистики для админ-панели
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.decorators import admin_required
from bot.services.database_service import (
    get_all_themes,
    get_all_book_authors,
    get_all_lesson_teachers,
    get_all_books,
    get_all_lessons,
    get_all_lesson_series,
    get_all_tests,
)

router = Router()


@router.callback_query(F.data == "admin_stats")
@admin_required
async def admin_stats(callback: CallbackQuery):
    """Показать статистику"""
    themes = await get_all_themes()
    authors = await get_all_book_authors()
    teachers = await get_all_lesson_teachers()
    books = await get_all_books()
    series = await get_all_lesson_series()
    lessons = await get_all_lessons()
    tests = await get_all_tests()

    active_themes = len([t for t in themes if t.is_active])
    active_authors = len([a for a in authors if a.is_active])
    active_teachers = len([t for t in teachers if t.is_active])
    active_books = len([b for b in books if b.is_active])
    active_series = len([s for s in series if s.is_active])
    active_lessons = len([l for l in lessons if l.is_active])
    active_tests = len([t for t in tests if t.is_active])

    # Подсчет общей длительности в секундах и конвертация в минуты
    total_duration_seconds = sum(l.duration_seconds or 0 for l in lessons if l.is_active)
    total_duration_minutes = total_duration_seconds // 60
    total_duration_hours = total_duration_minutes // 60
    remaining_minutes = total_duration_minutes % 60

    duration_text = f"{total_duration_hours}ч {remaining_minutes}м" if total_duration_hours > 0 else f"{total_duration_minutes}м"

    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"📚 Темы: {active_themes}/{len(themes)}\n"
        f"✍️ Авторы: {active_authors}/{len(authors)}\n"
        f"👤 Преподаватели: {active_teachers}/{len(teachers)}\n"
        f"📖 Книги: {active_books}/{len(books)}\n"
        f"📁 Серии: {active_series}/{len(series)}\n"
        f"🎧 Уроки: {active_lessons}/{len(lessons)}\n"
        f"🎓 Тесты: {active_tests}/{len(tests)}\n"
        f"⏱️ Общая длительность: {duration_text}\n\n"
        f"🔥 Активные элементы / Всего элементов"
    )

    await callback.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]])
    )
    await callback.answer()
