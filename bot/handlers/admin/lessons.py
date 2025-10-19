"""
Обработчики управления уроками для администраторов
"""
import os
import re
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required
from bot.utils.audio_converter import convert_to_mp3_auto, get_audio_duration
from bot.utils.formatters import format_duration, format_file_size
from bot.utils.config import config
from bot.services.database_service import (
    get_all_lessons,
    get_all_books,
    get_all_themes,
    get_all_lesson_teachers,
    get_lesson_by_id,
    get_lesson_teacher_by_id,
    get_book_by_id,
    create_lesson,
    update_lesson,
    delete_lesson
)
from bot.models.lesson import Lesson
from bot.models.book import Book
from bot.models.database import async_session_maker
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload, joinedload

logger = logging.getLogger(__name__)

router = Router()


class LessonStates(StatesGroup):
    """Состояния для управления уроками"""
    title = State()
    description = State()
    series_year = State()
    series_name = State()
    book_id = State()
    theme_id = State()
    teacher_id = State()
    lesson_number = State()
    tags = State()
    audio_file = State()
    replace_audio = State()  # Для замены аудиофайла


@router.callback_query(F.data == "admin_lessons")
@admin_required
async def admin_lessons(callback: CallbackQuery):
    """Показать список преподавателей для управления уроками"""
    teachers = await get_all_lesson_teachers()

    builder = InlineKeyboardBuilder()
    for teacher in teachers:
        # Подсчитываем количество уроков преподавателя
        lessons = await get_all_lessons()
        teacher_lessons_count = len([l for l in lessons if l.teacher_id == teacher.id])

        builder.add(InlineKeyboardButton(
            text=f"👤 {teacher.name} ({teacher_lessons_count} урок.)",
            callback_data=f"lessons_teacher_{teacher.id}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)

    await callback.message.edit_text(
        "🎧 <b>Управление уроками</b>\n\n"
        "Выберите преподавателя:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lessons_teacher_"))
@admin_required
async def show_teacher_themes(callback: CallbackQuery):
    """Показать темы с уроками выбранного преподавателя"""
    teacher_id = int(callback.data.split("_")[2])

    # Получаем все уроки преподавателя
    async with async_session_maker() as session:
        session.expire_on_commit = False
        result = await session.execute(
            select(Lesson)
            .where(Lesson.teacher_id == teacher_id)
            .options(
                joinedload(Lesson.book).joinedload(Book.theme),
                joinedload(Lesson.theme)
            )
        )
        teacher_lessons = result.scalars().unique().all()

    # Собираем данные по темам
    theme_data = {}
    lessons_without_theme = 0

    for lesson in teacher_lessons:
        effective_theme_id = lesson.effective_theme_id

        if effective_theme_id:
            # Урок имеет тему (либо через книгу, либо напрямую)
            if effective_theme_id not in theme_data:
                effective_theme = lesson.effective_theme
                theme_data[effective_theme_id] = {
                    "id": effective_theme_id,
                    "name": effective_theme.name if effective_theme else "Без названия",
                    "count": 0
                }
            theme_data[effective_theme_id]["count"] += 1
        else:
            # Урок без темы (book_id=NULL и theme_id=NULL, либо book без theme)
            lessons_without_theme += 1

    if not theme_data and lessons_without_theme == 0:
        await callback.message.edit_text(
            "❌ У этого преподавателя пока нет уроков",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data="admin_lessons")
            ]])
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()

    # Добавляем кнопку для уроков без темы (если есть)
    if lessons_without_theme > 0:
        builder.add(InlineKeyboardButton(
            text=f"📑 Без темы ({lessons_without_theme} урок.)",
            callback_data=f"lessons_no_theme_{teacher_id}"
        ))

    # Добавляем темы
    for theme in sorted(theme_data.values(), key=lambda x: x["name"]):
        builder.add(InlineKeyboardButton(
            text=f"📚 {theme['name']} ({theme['count']} урок.)",
            callback_data=f"lessons_theme_{teacher_id}_{theme['id']}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_lessons"))
    builder.adjust(1)

    # Получаем имя преподавателя
    teachers = await get_all_lesson_teachers()
    teacher = next((t for t in teachers if t.id == teacher_id), None)
    teacher_name = teacher.name if teacher else "Преподаватель"

    await callback.message.edit_text(
        f"🎧 <b>Уроки: {teacher_name}</b>\n\n"
        "Выберите тему:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^lessons_no_theme_\d+$"))
@admin_required
async def show_lessons_without_theme(callback: CallbackQuery):
    """Показать уроки без темы (effective_theme_id == None)"""
    teacher_id = int(callback.data.split("_")[3])

    # Получаем все уроки преподавателя
    async with async_session_maker() as session:
        session.expire_on_commit = False
        result = await session.execute(
            select(Lesson)
            .where(Lesson.teacher_id == teacher_id)
            .options(
                joinedload(Lesson.book).joinedload(Book.theme),
                joinedload(Lesson.theme)
            )
            .order_by(Lesson.series_year.desc(), Lesson.series_name)
        )
        all_lessons = result.scalars().unique().all()

    # Фильтруем уроки без темы
    lessons = [lesson for lesson in all_lessons if lesson.effective_theme_id is None]

    if not lessons:
        await callback.answer("В этой категории пока нет уроков", show_alert=True)
        return

    builder = InlineKeyboardBuilder()

    # Группируем по книгам
    book_map = {}
    lessons_without_book_count = 0

    for lesson in lessons:
        if lesson.book:
            book_id = lesson.book.id
            if book_id not in book_map:
                book_map[book_id] = {
                    "id": book_id,
                    "name": lesson.book.name,
                    "lessons": []
                }
            book_map[book_id]["lessons"].append(lesson)
        else:
            lessons_without_book_count += 1

    # Добавляем кнопку для уроков без книги (если есть)
    if lessons_without_book_count > 0:
        builder.add(InlineKeyboardButton(
            text=f"📕 Без книги ({lessons_without_book_count} урок.)",
            callback_data=f"lessons_no_theme_no_book_{teacher_id}"
        ))

    # Показываем список книг
    for book_id, book_data in sorted(book_map.items(), key=lambda x: x[1]["name"]):
        builder.add(InlineKeyboardButton(
            text=f"📖 {book_data['name']} ({len(book_data['lessons'])} урок.)",
            callback_data=f"lessons_no_theme_book_{teacher_id}_{book_id}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_teacher_{teacher_id}"))
    builder.adjust(1)

    await callback.message.edit_text(
        "📑 <b>Уроки без темы</b>\n\n"
        "Выберите книгу:",
        reply_markup=builder.as_markup()
    )

    await callback.answer()


@router.callback_query(F.data.startswith("lessons_no_theme_no_book_"))
@admin_required
async def show_no_theme_no_book_lessons(callback: CallbackQuery):
    """Показать уроки без темы и без книги"""
    teacher_id = int(callback.data.split("_")[5])

    # Получаем уроки без темы и без книги
    async with async_session_maker() as session:
        session.expire_on_commit = False
        result = await session.execute(
            select(Lesson)
            .where(and_(
                Lesson.teacher_id == teacher_id,
                Lesson.book_id == None,
                Lesson.theme_id == None
            ))
            .order_by(Lesson.series_year.desc(), Lesson.series_name, Lesson.lesson_number)
        )
        lessons = result.scalars().all()

    if not lessons:
        await callback.answer("Уроки не найдены", show_alert=True)
        return

    # Группируем по сериям
    series_map = {}
    for lesson in lessons:
        series_key = f"{lesson.series_year}_{lesson.series_name}"
        if series_key not in series_map:
            series_map[series_key] = {
                "year": lesson.series_year,
                "name": lesson.series_name,
                "lessons": []
            }
        series_map[series_key]["lessons"].append(lesson)

    builder = InlineKeyboardBuilder()

    # Если только одна серия - показываем сразу уроки
    if len(series_map) == 1:
        series_data = list(series_map.values())[0]
        for lesson in sorted(series_data["lessons"], key=lambda x: x.lesson_number or 0):
            lesson_num = f"#{lesson.lesson_number}" if lesson.lesson_number else "Без номера"
            builder.add(InlineKeyboardButton(
                text=f"{lesson_num} - {lesson.title}",
                callback_data=f"edit_lesson_{lesson.id}"
            ))

        builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
        builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_no_theme_{teacher_id}"))
        builder.adjust(1)

        await callback.message.edit_text(
            f"📑 <b>Без темы</b>\n"
            f"📕 Без книги\n"
            f"📚 Серия: {series_data['year']} - {series_data['name']}\n\n"
            "Выберите урок:",
            reply_markup=builder.as_markup()
        )
    else:
        # Несколько серий - показываем список серий
        for series_key in sorted(series_map.keys(), key=lambda x: (-series_map[x]["year"], series_map[x]["name"])):
            series_data = series_map[series_key]
            builder.add(InlineKeyboardButton(
                text=f"📚 {series_data['year']} - {series_data['name']} ({len(series_data['lessons'])} урок.)",
                callback_data=f"lessons_no_theme_no_book_series_{teacher_id}_{series_data['year']}_{series_data['name']}"
            ))

        builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
        builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_no_theme_{teacher_id}"))
        builder.adjust(1)

        await callback.message.edit_text(
            f"📑 <b>Без темы</b>\n"
            f"📕 Без книги\n\n"
            "Выберите серию:",
            reply_markup=builder.as_markup()
        )

    await callback.answer()


@router.callback_query(F.data.startswith("lessons_no_theme_book_"))
@admin_required
async def show_no_theme_book_series(callback: CallbackQuery):
    """Показать серии уроков для книги без темы"""
    parts = callback.data.split("_")
    teacher_id = int(parts[4])
    book_id = int(parts[5])

    # Получаем уроки для данной книги
    async with async_session_maker() as session:
        session.expire_on_commit = False
        result = await session.execute(
            select(Lesson)
            .where(and_(
                Lesson.teacher_id == teacher_id,
                Lesson.book_id == book_id
            ))
            .options(joinedload(Lesson.book))
            .order_by(Lesson.series_year.desc(), Lesson.series_name, Lesson.lesson_number)
        )
        lessons = result.scalars().unique().all()

    if not lessons:
        await callback.answer("Уроки не найдены", show_alert=True)
        return

    book_name = lessons[0].book.name if lessons[0].book else "Неизвестная книга"

    # Группируем по сериям
    series_map = {}
    for lesson in lessons:
        series_key = f"{lesson.series_year}_{lesson.series_name}"
        if series_key not in series_map:
            series_map[series_key] = {
                "year": lesson.series_year,
                "name": lesson.series_name,
                "lessons": []
            }
        series_map[series_key]["lessons"].append(lesson)

    builder = InlineKeyboardBuilder()

    # Если только одна серия - сразу показываем уроки
    if len(series_map) == 1:
        series_data = list(series_map.values())[0]
        for lesson in sorted(series_data["lessons"], key=lambda x: x.lesson_number or 0):
            lesson_num = f"#{lesson.lesson_number}" if lesson.lesson_number else "Без номера"
            builder.add(InlineKeyboardButton(
                text=f"{lesson_num} - {lesson.title}",
                callback_data=f"edit_lesson_{lesson.id}"
            ))

        builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
        builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_no_theme_{teacher_id}"))
        builder.adjust(1)

        await callback.message.edit_text(
            f"📖 <b>{book_name}</b>\n"
            f"📚 Серия: {series_data['year']} - {series_data['name']}\n\n"
            "Выберите урок:",
            reply_markup=builder.as_markup()
        )
    else:
        # Несколько серий - показываем список серий
        for series_key in sorted(series_map.keys(), key=lambda x: (-series_map[x]["year"], series_map[x]["name"])):
            series_data = series_map[series_key]
            builder.add(InlineKeyboardButton(
                text=f"📚 {series_data['year']} - {series_data['name']} ({len(series_data['lessons'])} урок.)",
                callback_data=f"lessons_no_theme_series_{teacher_id}_{book_id}_{series_data['year']}_{series_data['name']}"
            ))

        builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
        builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_no_theme_{teacher_id}"))
        builder.adjust(1)

        await callback.message.edit_text(
            f"📖 <b>{book_name}</b>\n\n"
            "Выберите серию:",
            reply_markup=builder.as_markup()
        )

    await callback.answer()


@router.callback_query(F.data.startswith("lessons_no_theme_series_"))
@admin_required
async def show_no_theme_series_lessons(callback: CallbackQuery):
    """Показать уроки серии для книги без темы"""
    parts = callback.data.split("_")
    teacher_id = int(parts[4])
    book_id = int(parts[5])
    series_year = int(parts[6])
    series_name = "_".join(parts[7:])  # Название серии может содержать подчеркивания

    # Получаем уроки данной серии
    async with async_session_maker() as session:
        session.expire_on_commit = False
        result = await session.execute(
            select(Lesson)
            .where(and_(
                Lesson.teacher_id == teacher_id,
                Lesson.book_id == book_id,
                Lesson.series_year == series_year,
                Lesson.series_name == series_name
            ))
            .options(joinedload(Lesson.book))
            .order_by(Lesson.lesson_number)
        )
        lessons = result.scalars().unique().all()

    if not lessons:
        await callback.answer("Уроки не найдены", show_alert=True)
        return

    book_name = lessons[0].book.name if lessons[0].book else "Неизвестная книга"

    builder = InlineKeyboardBuilder()

    for lesson in lessons:
        lesson_num = f"#{lesson.lesson_number}" if lesson.lesson_number else "Без номера"
        builder.add(InlineKeyboardButton(
            text=f"{lesson_num} - {lesson.title}",
            callback_data=f"edit_lesson_{lesson.id}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_no_theme_book_{teacher_id}_{book_id}"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"📖 <b>{book_name}</b>\n"
        f"📚 Серия: {series_year} - {series_name}\n\n"
        "Выберите урок:",
        reply_markup=builder.as_markup()
    )

    await callback.answer()


@router.callback_query(F.data.regexp(r"^lessons_theme_\d+_\d+$"))
@admin_required
async def show_theme_books(callback: CallbackQuery):
    """Показать книги в выбранной теме для данного преподавателя"""
    parts = callback.data.split("_")
    teacher_id = int(parts[2])
    theme_id = int(parts[3])

    # Получаем уроки преподавателя в данной теме
    async with async_session_maker() as session:
        session.expire_on_commit = False
        result = await session.execute(
            select(Lesson)
            .where(Lesson.teacher_id == teacher_id)
            .options(
                joinedload(Lesson.book).joinedload(Book.theme),
                joinedload(Lesson.theme)
            )
        )
        teacher_lessons = result.scalars().unique().all()

        # Фильтруем книги по теме и собираем данные
        book_data = {}
        theme_name = None
        lessons_without_book = 0

        for lesson in teacher_lessons:
            # Проверяем что урок относится к этой теме
            if lesson.effective_theme_id == theme_id:
                if theme_name is None:
                    effective_theme = lesson.effective_theme
                    if effective_theme:
                        theme_name = effective_theme.name

                if lesson.book:
                    # Урок с книгой
                    book_id = lesson.book.id
                    if book_id not in book_data:
                        book_data[book_id] = {
                            "id": book_id,
                            "name": lesson.book.name,
                            "count": 0
                        }
                    book_data[book_id]["count"] += 1
                else:
                    # Урок без книги, но с темой
                    lessons_without_book += 1

    if not book_data and lessons_without_book == 0:
        await callback.message.edit_text(
            "❌ В этой теме пока нет книг с уроками данного преподавателя",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_teacher_{teacher_id}")
            ]])
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()

    # Добавляем кнопку для уроков без книги в этой теме (если есть)
    if lessons_without_book > 0:
        builder.add(InlineKeyboardButton(
            text=f"📕 Без книги ({lessons_without_book} урок.)",
            callback_data=f"lessons_theme_no_book_{teacher_id}_{theme_id}"
        ))

    for book in sorted(book_data.values(), key=lambda x: x["name"]):
        builder.add(InlineKeyboardButton(
            text=f"📖 {book['name']} ({book['count']} урок.)",
            callback_data=f"lessons_book_{teacher_id}_{theme_id}_{book['id']}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_teacher_{teacher_id}"))
    builder.adjust(1)

    # Получаем имя преподавателя
    teachers = await get_all_lesson_teachers()
    teacher = next((t for t in teachers if t.id == teacher_id), None)
    teacher_name = teacher.name if teacher else "Преподаватель"

    # Используем название темы, полученное из сессии
    if theme_name is None:
        themes = await get_all_themes()
        theme = next((t for t in themes if t.id == theme_id), None)
        theme_name = theme.name if theme else "Тема"

    await callback.message.edit_text(
        f"🎧 <b>Уроки: {teacher_name}</b>\n"
        f"📚 Тема: {theme_name}\n\n"
        "Выберите книгу:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lessons_theme_no_book_"))
@admin_required
async def show_theme_lessons_without_book(callback: CallbackQuery):
    """Показать уроки без книги в рамках конкретной темы"""
    parts = callback.data.split("_")
    teacher_id = int(parts[4])
    theme_id = int(parts[5])

    # Получаем уроки без книги в этой теме
    async with async_session_maker() as session:
        session.expire_on_commit = False
        result = await session.execute(
            select(Lesson)
            .where(and_(
                Lesson.teacher_id == teacher_id,
                Lesson.book_id == None,
                Lesson.theme_id == theme_id
            ))
            .options(joinedload(Lesson.theme))
            .order_by(Lesson.series_year.desc(), Lesson.series_name, Lesson.lesson_number)
        )
        lessons = result.scalars().all()

        # Группируем по сериям
        series_map = {}
        theme_name = None

        for lesson in lessons:
            if theme_name is None and lesson.theme:
                theme_name = lesson.theme.name

            series_key = f"{lesson.series_year}_{lesson.series_name}"
            if series_key not in series_map:
                series_map[series_key] = {
                    "year": lesson.series_year,
                    "name": lesson.series_name,
                    "lessons": []
                }
            series_map[series_key]["lessons"].append({
                "id": lesson.id,
                "title": lesson.title,
                "lesson_number": lesson.lesson_number,
                "is_active": lesson.is_active
            })

    if not series_map:
        await callback.message.edit_text(
            "❌ Нет уроков без книги в этой теме",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_theme_{teacher_id}_{theme_id}")
            ]])
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()

    # Если только одна серия - показываем сразу уроки
    if len(series_map) == 1:
        series_data = list(series_map.values())[0]
        for lesson_data in series_data["lessons"]:
            lesson_title = f"🎧 Урок {lesson_data['lesson_number']}: {lesson_data['title']}" if lesson_data['lesson_number'] else f"🎧 {lesson_data['title']}"
            if not lesson_data['is_active']:
                lesson_title += " ❌"

            builder.add(InlineKeyboardButton(
                text=lesson_title,
                callback_data=f"edit_lesson_{lesson_data['id']}"
            ))

        builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
        builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_theme_{teacher_id}_{theme_id}"))
        builder.adjust(1)

        await callback.message.edit_text(
            f"📑 <b>{theme_name or 'Тема'}</b>\n"
            f"📕 Без книги\n"
            f"📚 Серия: {series_data['year']} - {series_data['name']}\n\n"
            f"Всего уроков: {len(series_data['lessons'])}",
            reply_markup=builder.as_markup()
        )
    else:
        # Несколько серий - показываем список серий
        for series_key in sorted(series_map.keys(), key=lambda x: (-series_map[x]["year"], series_map[x]["name"])):
            series_data = series_map[series_key]
            builder.add(InlineKeyboardButton(
                text=f"📚 {series_data['year']} - {series_data['name']} ({len(series_data['lessons'])} урок.)",
                callback_data=f"lessons_theme_no_book_series_{teacher_id}_{theme_id}_{series_data['year']}_{series_data['name']}"
            ))

        builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
        builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_theme_{teacher_id}_{theme_id}"))
        builder.adjust(1)

        await callback.message.edit_text(
            f"📑 <b>{theme_name or 'Тема'}</b>\n"
            f"📕 Без книги\n\n"
            "Выберите серию:",
            reply_markup=builder.as_markup()
        )

    await callback.answer()


@router.callback_query(F.data.regexp(r"^lessons_book_\d+_\d+_\d+$"))
@admin_required
async def show_book_series(callback: CallbackQuery):
    """Показать серии уроков для выбранной книги"""
    parts = callback.data.split("_")
    teacher_id = int(parts[2])
    theme_id = int(parts[3])
    book_id = int(parts[4])

    # Получаем уроки преподавателя по данной книге
    async with async_session_maker() as session:
        result = await session.execute(
            select(Lesson).where(
                and_(
                    Lesson.teacher_id == teacher_id,
                    Lesson.book_id == book_id
                )
            ).options(selectinload(Lesson.book))
        )
        book_lessons = result.scalars().all()

        # Группируем уроки по сериям (год + название) внутри сессии
        series_map = {}
        book_name = None
        for lesson in book_lessons:
            if book_name is None and lesson.book:
                book_name = lesson.book.name

            series_key = f"{lesson.series_year}_{lesson.series_name}"
            if series_key not in series_map:
                series_map[series_key] = {
                    "year": lesson.series_year,
                    "name": lesson.series_name,
                    "count": 0
                }
            series_map[series_key]["count"] += 1

    if not series_map:
        await callback.message.edit_text(
            "❌ По этой книге пока нет уроков данного преподавателя",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_theme_{teacher_id}_{theme_id}")
            ]])
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    # Сортируем серии по году (новые первыми) и названию
    for series_key in sorted(series_map.keys(), key=lambda x: (-series_map[x]["year"], series_map[x]["name"])):
        series_data = series_map[series_key]

        builder.add(InlineKeyboardButton(
            text=f"📚 {series_data['year']} - {series_data['name']} ({series_data['count']} урок.)",
            callback_data=f"lessons_series_{teacher_id}_{theme_id}_{book_id}_{series_data['year']}_{series_data['name']}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_theme_{teacher_id}_{theme_id}"))
    builder.adjust(1)

    # Получаем имя преподавателя
    teachers = await get_all_lesson_teachers()
    teacher = next((t for t in teachers if t.id == teacher_id), None)
    teacher_name = teacher.name if teacher else "Преподаватель"

    # Используем название книги из сессии
    if book_name is None:
        books = await get_all_books()
        book = next((b for b in books if b.id == book_id), None)
        book_name = book.name if book else "Книга"

    await callback.message.edit_text(
        f"🎧 <b>Уроки: {teacher_name}</b>\n"
        f"📖 Книга: {book_name}\n\n"
        "Выберите серию:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lessons_series_"))
@admin_required
async def show_series_lessons(callback: CallbackQuery):
    """Показать уроки в выбранной серии"""
    parts = callback.data.split("_")
    teacher_id = int(parts[2])
    theme_id = int(parts[3])
    book_id = int(parts[4])
    series_year = int(parts[5])
    # Название серии может содержать подчеркивания, берем все оставшиеся части
    series_name = "_".join(parts[6:])

    # Получаем уроки данной серии
    async with async_session_maker() as session:
        result = await session.execute(
            select(Lesson).where(
                and_(
                    Lesson.teacher_id == teacher_id,
                    Lesson.book_id == book_id,
                    Lesson.series_year == series_year,
                    Lesson.series_name == series_name
                )
            ).order_by(Lesson.lesson_number)
            .options(selectinload(Lesson.book))
        )
        series_lessons = result.scalars().all()

        # Собираем данные уроков внутри сессии
        lessons_data = []
        book_name = None
        for lesson in series_lessons:
            if book_name is None and lesson.book:
                book_name = lesson.book.name

            lessons_data.append({
                "id": lesson.id,
                "title": lesson.title,
                "lesson_number": lesson.lesson_number,
                "is_active": lesson.is_active
            })

    if not lessons_data:
        await callback.message.edit_text(
            "❌ В этой серии пока нет уроков",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_book_{teacher_id}_{theme_id}_{book_id}")
            ]])
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for lesson_data in lessons_data:
        lesson_title = f"🎧 Урок {lesson_data['lesson_number']}: {lesson_data['title']}" if lesson_data['lesson_number'] else f"🎧 {lesson_data['title']}"

        # Добавляем статус активности
        if not lesson_data['is_active']:
            lesson_title += " ❌"

        builder.add(InlineKeyboardButton(
            text=lesson_title,
            callback_data=f"edit_lesson_{lesson_data['id']}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_book_{teacher_id}_{theme_id}_{book_id}"))
    builder.adjust(1)

    # Получаем имя преподавателя
    teachers = await get_all_lesson_teachers()
    teacher = next((t for t in teachers if t.id == teacher_id), None)
    teacher_name = teacher.name if teacher else "Преподаватель"

    # Используем название книги из сессии
    if book_name is None:
        books = await get_all_books()
        book = next((b for b in books if b.id == book_id), None)
        book_name = book.name if book else "Книга"

    await callback.message.edit_text(
        f"🎧 <b>Уроки: {teacher_name}</b>\n"
        f"📖 Книга: {book_name}\n"
        f"📚 Серия: {series_year} - {series_name}\n\n"
        f"Всего уроков: {len(lessons_data)}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_lesson")
@admin_required
async def add_lesson_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление нового урока"""
    # Получаем список книг и преподавателей
    books = await get_all_books()
    teachers = await get_all_lesson_teachers()

    if not books or not teachers:
        await callback.message.edit_text(
            "❌ Для добавления урока нужно сначала создать хотя бы одну книгу и одного преподавателя",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_lessons")]])
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Введите название урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.title)
    await callback.answer()


@router.message(LessonStates.title)
@admin_required
async def add_lesson_title(message: Message, state: FSMContext):
    """Сохранить название урока"""
    await state.update_data(title=message.text)

    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Введите описание урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_lesson_description")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]
        ])
    )
    await state.set_state(LessonStates.description)


@router.callback_query(F.data == "skip_lesson_description")
@admin_required
async def add_lesson_skip_description(callback: CallbackQuery, state: FSMContext):
    """Пропустить описание урока"""
    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Введите год серии уроков (например: 2024):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.series_year)
    await callback.answer()


@router.message(LessonStates.description)
@admin_required
async def add_lesson_description(message: Message, state: FSMContext):
    """Сохранить описание урока"""
    await state.update_data(description=message.text)

    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Введите год серии уроков (например: 2024):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.series_year)


@router.message(LessonStates.series_year)
@admin_required
async def add_lesson_series_year(message: Message, state: FSMContext):
    """Сохранить год серии"""
    try:
        year = int(message.text)
        if year < 2000 or year > 2050:
            await message.answer(
                "❌ Год должен быть в диапазоне 2000-2050. Попробуйте еще раз:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
            )
            return

        await state.update_data(series_year=year)

        await message.answer(
            "📝 <b>Добавление нового урока</b>\n\n"
            "Введите название серии (например: мечеть, фаида):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )
        await state.set_state(LessonStates.series_name)
    except ValueError:
        await message.answer(
            "❌ Год должен быть числом. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )


@router.message(LessonStates.series_name)
@admin_required
async def add_lesson_series_name(message: Message, state: FSMContext):
    """Сохранить название серии"""
    await state.update_data(series_name=message.text)

    # Получаем список книг
    books = await get_all_books()

    builder = InlineKeyboardBuilder()
    for book in books:
        builder.add(InlineKeyboardButton(text=book.name, callback_data=f"select_book_{book.id}"))

    # Кнопка "Нет книги"
    builder.add(InlineKeyboardButton(text="📕 Нет книги", callback_data="select_book_none"))
    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons"))
    builder.adjust(1)

    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Выберите книгу для урока или пропустите:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(LessonStates.book_id)


@router.callback_query(F.data.startswith("select_book_"))
@admin_required
async def select_book_for_lesson(callback: CallbackQuery, state: FSMContext):
    """Выбрать книгу для урока"""
    # Проверяем, выбрана ли опция "Нет книги"
    if callback.data == "select_book_none":
        book_id = None
        await state.update_data(book_id=book_id)

        # Если нет книги - предлагаем выбрать тему
        themes = await get_all_themes()

        builder = InlineKeyboardBuilder()
        for theme in themes:
            builder.add(InlineKeyboardButton(text=theme.name, callback_data=f"select_theme_{theme.id}"))

        builder.add(InlineKeyboardButton(text="📑 Без темы", callback_data="select_theme_none"))
        builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons"))
        builder.adjust(1)

        await callback.message.edit_text(
            "📝 <b>Добавление нового урока</b>\n\n"
            "Урок без книги. Выберите тему урока:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(LessonStates.theme_id)
        await callback.answer()
    else:
        book_id = int(callback.data.split("_")[2])
        await state.update_data(book_id=book_id, theme_id=None)  # Если есть книга, тема будет из книги

        # Получаем список преподавателей
        teachers = await get_all_lesson_teachers()

        builder = InlineKeyboardBuilder()
        for teacher in teachers:
            builder.add(InlineKeyboardButton(text=teacher.name, callback_data=f"select_teacher_{teacher.id}"))

        builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons"))
        builder.adjust(1)

        await callback.message.edit_text(
            "📝 <b>Добавление нового урока</b>\n\n"
            "Выберите преподавателя урока:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(LessonStates.teacher_id)
        await callback.answer()


@router.callback_query(F.data.startswith("select_theme_"))
@admin_required
async def select_theme_for_lesson(callback: CallbackQuery, state: FSMContext):
    """Выбрать тему для урока без книги"""
    if callback.data == "select_theme_none":
        theme_id = None
    else:
        theme_id = int(callback.data.split("_")[2])

    await state.update_data(theme_id=theme_id)

    # Получаем список преподавателей
    teachers = await get_all_lesson_teachers()

    builder = InlineKeyboardBuilder()
    for teacher in teachers:
        builder.add(InlineKeyboardButton(text=teacher.name, callback_data=f"select_teacher_{teacher.id}"))

    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons"))
    builder.adjust(1)

    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Выберите преподавателя урока:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(LessonStates.teacher_id)
    await callback.answer()


@router.callback_query(F.data.startswith("select_teacher_"))
@admin_required
async def select_teacher_for_lesson(callback: CallbackQuery, state: FSMContext):
    """Выбрать преподавателя для урока"""
    teacher_id = int(callback.data.split("_")[2])
    await state.update_data(teacher_id=teacher_id)

    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Введите номер урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.lesson_number)
    await callback.answer()


@router.message(LessonStates.lesson_number)
@admin_required
async def add_lesson_number(message: Message, state: FSMContext):
    """Сохранить номер урока"""
    try:
        lesson_number = int(message.text)
        await state.update_data(lesson_number=lesson_number)

        await message.answer(
            "📝 <b>Добавление нового урока</b>\n\n"
            "Введите теги для урока через запятую:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_lesson_tags")],
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]
            ])
        )
        await state.set_state(LessonStates.tags)
    except ValueError:
        await message.answer(
            "❌ Номер урока должен быть числом. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )


@router.callback_query(F.data == "skip_lesson_tags")
@admin_required
async def add_lesson_skip_tags(callback: CallbackQuery, state: FSMContext):
    """Пропустить теги урока"""
    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Отправьте аудиофайл урока\n\n"
        "📋 <b>Поддерживаемые форматы:</b>\n"
        "• MP3, WAV, FLAC, M4A, OGG, AAC, WMA и другие\n\n"
        "ℹ️ <b>Файл будет автоматически:</b>\n"
        "✓ Конвертирован в MP3 (оптимальное качество)\n"
        "✓ Нормализован по громкости\n"
        "✓ Битрейт подбирается автоматически (16-64 kbps)\n\n"
        "📏 <b>Максимальный размер: 20 МБ</b> (лимит Telegram Bot API)\n"
        "💡 <b>Рекомендация:</b> уроки до 40 минут в MP3 64kbps\n\n"
        "🌐 <b>Для больших файлов (до 2 ГБ) используйте для конвертации:</b>\n"
        f"{config.web_converter_url}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.audio_file)
    await callback.answer()


@router.message(LessonStates.tags)
@admin_required
async def add_lesson_tags(message: Message, state: FSMContext):
    """Сохранить теги урока"""
    await state.update_data(tags=message.text)

    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Отправьте аудиофайл урока\n\n"
        "📋 <b>Поддерживаемые форматы:</b>\n"
        "• MP3, WAV, FLAC, M4A, OGG, AAC, WMA и другие\n\n"
        "ℹ️ <b>Файл будет автоматически:</b>\n"
        "✓ Конвертирован в MP3 (оптимальное качество)\n"
        "✓ Нормализован по громкости\n"
        "✓ Битрейт подбирается автоматически (16-64 kbps)\n\n"
        "📏 <b>Максимальный размер: 20 МБ</b> (лимит Telegram Bot API)\n"
        "💡 <b>Рекомендация:</b> уроки до 40 минут в MP3 64kbps\n\n"
        "🌐 <b>Для больших файлов (до 2 ГБ) используйте для конвертации:</b>\n"
        f"{config.web_converter_url}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.audio_file)


@router.message(LessonStates.audio_file)
@admin_required
async def add_lesson_audio(message: Message, state: FSMContext):
    """Сохранить аудиофайл урока с автоматической конвертацией через FFmpeg"""
    data = await state.get_data()

    # Определяем тип медиа и получаем файл
    audio_file = None
    file_ext = None

    if message.audio:
        audio_file = message.audio
        file_ext = "mp3"
    elif message.voice:
        audio_file = message.voice
        file_ext = "ogg"
    elif message.document:
        audio_file = message.document

        # Определяем расширение из имени файла
        if audio_file.file_name:
            file_ext = audio_file.file_name.split('.')[-1].lower() if '.' in audio_file.file_name else "unknown"
        else:
            file_ext = "unknown"
    else:
        await message.answer(
            "❌ Пожалуйста, отправьте аудиофайл\n\n"
            "📋 Поддерживаемые форматы: MP3, WAV, FLAC, M4A, OGG, AAC и другие",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")
            ]])
        )
        return

    # Проверяем размер файла
    file_size_mb = audio_file.file_size / (1024 * 1024) if audio_file.file_size else 0
    logger.info(f"Получен аудиофайл: размер={file_size_mb:.2f} МБ, расширение={file_ext}")

    if file_size_mb > config.max_audio_size_mb:
        logger.warning(f"Файл отклонён: {file_size_mb:.2f} МБ > {config.max_audio_size_mb} МБ")
        await message.answer(
            f"❌ Файл слишком большой ({file_size_mb:.1f} МБ)\n\n"
            f"📏 Максимальный размер: {config.max_audio_size_mb} МБ (лимит Telegram Bot API)\n\n"
            f"🌐 Для больших файлов используйте для конвертации:\n"
            f"{config.web_converter_url}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")
            ]])
        )
        await state.clear()
        return

    # Показываем сообщение о начале обработки
    processing_msg = await message.answer("⏳ Скачивание аудио файла...")

    # Скачиваем аудиофайл
    try:
        file_info = await message.bot.get_file(audio_file.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)
    except Exception as e:
        await processing_msg.edit_text(
            f"❌ Ошибка при скачивании файла: {str(e)}\n\n"
            f"Попробуйте отправить файл меньшего размера.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")
            ]])
        )
        await state.clear()
        return

    # Создаём директории для аудио
    original_dir = "bot/audio_files/original"
    converted_dir = "bot/audio_files/converted"
    os.makedirs(original_dir, exist_ok=True)
    os.makedirs(converted_dir, exist_ok=True)

    # Сохраняем оригинальный файл
    original_path = os.path.join(original_dir, f"{audio_file.file_unique_id}.{file_ext}")
    with open(original_path, "wb") as f:
        f.write(downloaded_file.getvalue())

    logger.info(f"Оригинальный файл сохранён: {original_path}")

    # Обновляем сообщение о процессе
    if file_size_mb > 100:
        time_estimate = "несколько минут"
    elif file_size_mb > 500:
        time_estimate = "5-10 минут"
    else:
        time_estimate = "несколько секунд"

    await processing_msg.edit_text(
        f"⏳ Обработка аудио файла...\n\n"
        f"📊 Исходный размер: {format_file_size(audio_file.file_size)}\n"
        f"⏱ Примерное время: {time_estimate}\n\n"
        f"Пожалуйста, подождите..."
    )

    # Конвертируем в MP3 с автоматическим подбором битрейта
    converted_path = os.path.join(converted_dir, f"{audio_file.file_unique_id}.mp3")
    success, error, used_bitrate = await convert_to_mp3_auto(
        original_path,
        converted_path,
        preferred_bitrate=64  # Предпочтительный битрейт для хорошего качества
    )

    if not success:
        await processing_msg.edit_text(
            f"❌ Ошибка обработки аудио:\n\n{error}\n\n"
            "Попробуйте отправить файл в другом формате (MP3, WAV, FLAC) "
            "или разделите урок на части по 1-2 часа.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")
            ]])
        )
        # Удаляем оригинальный файл при ошибке
        if os.path.exists(original_path):
            os.remove(original_path)
        if os.path.exists(converted_path):
            os.remove(converted_path)
        await state.clear()
        return

    # Получаем длительность автоматически
    duration_seconds = await get_audio_duration(converted_path)

    if not duration_seconds:
        logger.warning(f"Не удалось определить длительность для {converted_path}")
        duration_seconds = 0

    # Создаём красивое имя файла на основе данных урока
    # Получаем данные для имени файла
    teacher = await get_lesson_teacher_by_id(data["teacher_id"]) if data.get("teacher_id") else None
    book = await get_book_by_id(data["book_id"]) if data.get("book_id") else None

    # Функция для очистки имени файла от недопустимых символов
    def sanitize_filename(name):
        """Удаляет недопустимые символы из имени файла"""
        if not name:
            return "unnamed"
        # Заменяем недопустимые символы на подчёркивание
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Убираем множественные пробелы и подчёркивания
        name = re.sub(r'[\s_]+', '_', name)
        # Ограничиваем длину
        return name[:50]

    # Формируем имя файла
    parts = []
    if teacher:
        parts.append(sanitize_filename(teacher.name))
    if book:
        parts.append(sanitize_filename(book.name))
    parts.append(f"{data['series_year']}")
    parts.append(sanitize_filename(data['series_name']))
    if data.get('lesson_number'):
        parts.append(f"урок_{data['lesson_number']}")

    new_filename = "_".join(parts) + ".mp3"
    new_converted_path = os.path.join(converted_dir, new_filename)

    # Переименовываем файл
    if os.path.exists(converted_path):
        os.rename(converted_path, new_converted_path)
        logger.info(f"Файл переименован: {converted_path} -> {new_converted_path}")
        converted_path = new_converted_path

    # Создаём урок в базе
    try:
        lesson = await create_lesson(
            title=data["title"],
            series_year=data["series_year"],
            series_name=data["series_name"],
            description=data.get("description", ""),
            audio_file_path=converted_path,  # Путь к MP3 с нормальным именем
            duration_seconds=duration_seconds,  # Автоматически определённая длительность
            lesson_number=data["lesson_number"],
            book_id=data.get("book_id"),
            theme_id=data.get("theme_id"),
            teacher_id=data["teacher_id"],
            tags=data.get("tags", ""),
            is_active=True
        )

        # Удаляем сообщение о обработке
        await processing_msg.delete()

        # Получаем размеры файлов
        mp3_size = os.path.getsize(converted_path)
        original_size = os.path.getsize(original_path)

        # Показываем успешный результат
        success_message = (
            f"✅ <b>Урок «{lesson.title}» успешно добавлен!</b>\n\n"
            f"📊 Длительность: {format_duration(duration_seconds)}\n"
            f"🎵 Битрейт MP3: {used_bitrate} kbps\n"
            f"💾 Размер MP3: {format_file_size(mp3_size)}\n"
            f"📁 Оригинал: {format_file_size(original_size)}"
        )

        # Если был использован битрейт ниже предпочтительного, добавляем пояснение
        if used_bitrate and used_bitrate < 64:
            success_message += (
                f"\n\nℹ️ Битрейт автоматически снижен до {used_bitrate} kbps "
                f"для соблюдения лимита 50 МБ"
            )

        await message.answer(
            success_message,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К списку уроков", callback_data="admin_lessons")
            ]])
        )

        logger.info(f"Урок создан: {lesson.id} - {lesson.title}, длительность: {duration_seconds}с")
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при создании урока: {str(e)}")
        await processing_msg.edit_text(
            f"❌ Ошибка при сохранении урока в базу данных:\n{str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")
            ]])
        )
        # Удаляем файлы при ошибке
        if os.path.exists(original_path):
            os.remove(original_path)
        if os.path.exists(converted_path):
            os.remove(converted_path)
        await state.clear()


@router.callback_query(F.data.regexp(r"^edit_lesson_\d+$"))
@admin_required
async def edit_lesson_menu(callback: CallbackQuery):
    """Показать меню редактирования урока"""
    lesson_id = int(callback.data.split("_")[2])
    lesson = await get_lesson_by_id(lesson_id)

    if not lesson:
        await callback.message.edit_text(
            "❌ Урок не найден",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data="admin_lessons")
            ]])
        )
        await callback.answer()
        return

    # Формируем информацию об уроке
    info = f"🎧 <b>{lesson.display_title}</b>\n\n"
    info += f"📚 Серия: {lesson.series_display}\n"
    info += f"📑 Тема: {lesson.theme_name}\n"
    info += f"📖 Книга: {lesson.book_title}\n"
    info += f"👤 Преподаватель: {lesson.teacher_name}\n"

    if lesson.description:
        info += f"📝 Описание: {lesson.description}\n"

    if lesson.duration_seconds:
        info += f"⏱ Длительность: {lesson.formatted_duration}\n"

    if lesson.tags:
        info += f"🏷 Теги: {lesson.tags}\n"

    info += f"\n📁 Аудиофайл: {'✅ Есть' if lesson.has_audio() else '❌ Нет'}\n"
    info += f"{'✅ Активен' if lesson.is_active else '❌ Неактивен'}"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"edit_lesson_title_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Редактировать описание", callback_data=f"edit_lesson_description_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Изменить книгу", callback_data=f"edit_lesson_book_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Изменить тему", callback_data=f"edit_lesson_theme_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Изменить преподавателя", callback_data=f"edit_lesson_teacher_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Изменить год серии", callback_data=f"edit_lesson_year_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Изменить название серии", callback_data=f"edit_lesson_series_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Изменить номер урока", callback_data=f"edit_lesson_number_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Изменить теги", callback_data=f"edit_lesson_tags_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="🎵 Заменить аудиофайл", callback_data=f"replace_lesson_audio_{lesson.id}"))

    if lesson.is_active:
        builder.add(InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"toggle_lesson_active_{lesson.id}"))
    else:
        builder.add(InlineKeyboardButton(text="✅ Активировать", callback_data=f"toggle_lesson_active_{lesson.id}"))

    builder.add(InlineKeyboardButton(text="🗑 Удалить урок", callback_data=f"delete_lesson_{lesson.id}"))

    # Кнопка назад - просто к управлению уроками
    builder.add(InlineKeyboardButton(text="🔙 К управлению уроками", callback_data="admin_lessons"))
    builder.adjust(1)

    await callback.message.edit_text(
        info,
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^edit_lesson_book_\d+$"))
@admin_required
async def edit_lesson_book_handler(callback: CallbackQuery):
    """Изменить книгу урока"""
    lesson_id = int(callback.data.split("_")[3])
    lesson = await get_lesson_by_id(lesson_id)

    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    # Получаем все книги
    books = await get_all_books()

    builder = InlineKeyboardBuilder()
    for book in books:
        builder.add(InlineKeyboardButton(
            text=book.name,
            callback_data=f"update_lesson_book_{lesson_id}_{book.id}"
        ))

    builder.add(InlineKeyboardButton(text="📕 Без книги", callback_data=f"update_lesson_book_{lesson_id}_none"))
    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_lesson_{lesson_id}"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"📖 <b>Изменить книгу урока</b>\n\n"
        f"Текущая книга: {lesson.book_title}\n\n"
        "Выберите новую книгу:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("update_lesson_book_"))
@admin_required
async def update_lesson_book_handler(callback: CallbackQuery):
    """Обновить книгу урока"""
    parts = callback.data.split("_")
    lesson_id = int(parts[3])
    book_id = None if parts[4] == "none" else int(parts[4])

    lesson = await get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    lesson.book_id = book_id
    # Если выбрали книгу, удаляем theme_id (тема будет из книги)
    if book_id:
        lesson.theme_id = None

    await update_lesson(lesson)
    await callback.answer("✅ Книга обновлена")

    # Возвращаемся в меню редактирования
    await edit_lesson_menu(callback)


@router.callback_query(F.data.regexp(r"^edit_lesson_theme_\d+$"))
@admin_required
async def edit_lesson_theme_handler(callback: CallbackQuery):
    """Изменить тему урока (только для уроков без книги)"""
    lesson_id = int(callback.data.split("_")[3])
    lesson = await get_lesson_by_id(lesson_id)

    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    if lesson.book_id:
        await callback.answer("❌ Нельзя изменить тему, так как урок привязан к книге. Сначала уберите книгу.", show_alert=True)
        return

    # Получаем все темы
    themes = await get_all_themes()

    builder = InlineKeyboardBuilder()
    for theme in themes:
        builder.add(InlineKeyboardButton(
            text=theme.name,
            callback_data=f"update_lesson_theme_{lesson_id}_{theme.id}"
        ))

    builder.add(InlineKeyboardButton(text="📑 Без темы", callback_data=f"update_lesson_theme_{lesson_id}_none"))
    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_lesson_{lesson_id}"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"📑 <b>Изменить тему урока</b>\n\n"
        f"Текущая тема: {lesson.theme_name}\n\n"
        "Выберите новую тему:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("update_lesson_theme_"))
@admin_required
async def update_lesson_theme_handler(callback: CallbackQuery):
    """Обновить тему урока"""
    parts = callback.data.split("_")
    lesson_id = int(parts[3])
    theme_id = None if parts[4] == "none" else int(parts[4])

    lesson = await get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    if lesson.book_id:
        await callback.answer("❌ Нельзя изменить тему, так как урок привязан к книге", show_alert=True)
        return

    lesson.theme_id = theme_id
    await update_lesson(lesson)
    await callback.answer("✅ Тема обновлена")

    # Возвращаемся в меню редактирования
    await edit_lesson_menu(callback)


@router.callback_query(F.data.regexp(r"^edit_lesson_teacher_\d+$"))
@admin_required
async def edit_lesson_teacher_handler(callback: CallbackQuery):
    """Изменить преподавателя урока"""
    lesson_id = int(callback.data.split("_")[3])
    lesson = await get_lesson_by_id(lesson_id)

    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    # Получаем всех преподавателей
    teachers = await get_all_lesson_teachers()

    builder = InlineKeyboardBuilder()
    for teacher in teachers:
        builder.add(InlineKeyboardButton(
            text=teacher.name,
            callback_data=f"update_lesson_teacher_{lesson_id}_{teacher.id}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_lesson_{lesson_id}"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"👤 <b>Изменить преподавателя урока</b>\n\n"
        f"Текущий преподаватель: {lesson.teacher_name}\n\n"
        "Выберите нового преподавателя:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("update_lesson_teacher_"))
@admin_required
async def update_lesson_teacher_handler(callback: CallbackQuery):
    """Обновить преподавателя урока"""
    parts = callback.data.split("_")
    lesson_id = int(parts[3])
    teacher_id = int(parts[4])

    lesson = await get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    lesson.teacher_id = teacher_id
    await update_lesson(lesson)
    await callback.answer("✅ Преподаватель обновлён")

    # Возвращаемся в меню редактирования
    await edit_lesson_menu(callback)


@router.callback_query(F.data.startswith("delete_lesson_"))
@admin_required
async def delete_lesson_handler(callback: CallbackQuery):
    """Подтверждение удаления урока"""
    lesson_id = int(callback.data.split("_")[-1])

    lesson = await get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="✅ Да, удалить навсегда",
        callback_data=f"confirm_delete_lesson_{lesson_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=f"lesson_{lesson_id}"
    ))
    builder.adjust(1)

    # Форматируем длительность
    duration_text = lesson.formatted_duration if lesson.duration_seconds else "Неизвестна"

    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"Вы действительно хотите удалить урок?\n\n"
        f"<b>Название:</b> {lesson.title}\n"
        f"<b>Длительность:</b> {duration_text}\n\n"
        f"⚠️ <b>Это действие необратимо!</b>",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_lesson_"))
@admin_required
async def confirm_delete_lesson_handler(callback: CallbackQuery):
    """Подтвердить удаление урока"""
    lesson_id = int(callback.data.split("_")[-1])

    lesson = await get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    # Сохраняем информацию о серии для проверки
    series_year = lesson.series_year
    series_name = lesson.series_name
    teacher_id = lesson.teacher_id
    book_id = lesson.book_id

    # Удаляем аудиофайл, если есть
    if lesson.audio_path:
        import os
        audio_path = os.path.join(config.audio_files_path, lesson.audio_path)
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
                logger.info(f"Удалён аудиофайл: {audio_path}")
            except Exception as e:
                logger.error(f"Ошибка при удалении файла {audio_path}: {e}")

    # Удаляем урок из БД
    await delete_lesson(lesson_id)

    # Проверяем, остались ли ещё уроки в этой серии
    async with async_session_maker() as session:
        remaining_lessons = await session.execute(
            select(Lesson).where(
                and_(
                    Lesson.series_year == series_year,
                    Lesson.series_name == series_name,
                    Lesson.teacher_id == teacher_id,
                    Lesson.book_id == book_id
                )
            )
        )
        remaining_count = len(remaining_lessons.scalars().all())

    # Формируем сообщение
    message = f"✅ <b>Урок успешно удалён</b>\n\n" \
              f"Удалён урок: {lesson.title}\n" \
              f"Серия: {series_year} - {series_name}"

    if remaining_count == 0:
        message += f"\n\n⚠️ <b>Это был последний урок в серии!</b>\n" \
                   f"Серия '{series_year} - {series_name}' больше не содержит уроков."

    await callback.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 К управлению уроками", callback_data="admin_lessons")
        ]])
    )
    await callback.answer("✅ Урок удалён")


@router.callback_query(F.data.startswith("replace_lesson_audio_"))
@admin_required
async def replace_lesson_audio_handler(callback: CallbackQuery, state: FSMContext):
    """Начать процесс замены аудиофайла урока"""
    lesson_id = int(callback.data.split("_")[-1])
    lesson = await get_lesson_by_id(lesson_id)

    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    # Сохраняем ID урока в состоянии
    await state.update_data(lesson_id=lesson_id)
    await state.set_state(LessonStates.replace_audio)

    # Показываем информацию о текущем аудиофайле
    info = f"🎵 <b>Замена аудиофайла</b>\n\n"
    info += f"<b>Урок:</b> {lesson.display_title}\n"
    info += f"<b>Серия:</b> {lesson.series_display}\n\n"

    if lesson.audio_path:
        if lesson.duration_seconds:
            info += f"<b>Текущий файл:</b>\n"
            info += f"⏱ Длительность: {lesson.formatted_duration}\n"
            info += f"📁 Файл: {os.path.basename(lesson.audio_path)}\n\n"
        else:
            info += f"<b>Текущий файл:</b> {os.path.basename(lesson.audio_path)}\n\n"
    else:
        info += "⚠️ У урока пока нет аудиофайла\n\n"

    info += "📤 <b>Отправьте новый аудиофайл</b>\n\n"
    info += "📋 Поддерживаемые форматы: MP3, WAV, FLAC, M4A, OGG, AAC и другие\n"
    info += f"📏 Максимальный размер: {config.max_audio_size_mb} МБ\n\n"
    info += f"🌐 Для файлов больше {config.max_audio_size_mb} МБ используйте для конвертации:\n{config.web_converter_url}"

    await callback.message.edit_text(
        info,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_lesson_{lesson.id}")
        ]])
    )
    await callback.answer()


@router.message(LessonStates.replace_audio)
@admin_required
async def replace_lesson_audio_file(message: Message, state: FSMContext):
    """Обработка нового аудиофайла для замены"""
    data = await state.get_data()
    lesson_id = data.get("lesson_id")

    if not lesson_id:
        await message.answer("❌ Ошибка: ID урока не найден")
        await state.clear()
        return

    lesson = await get_lesson_by_id(lesson_id)
    if not lesson:
        await message.answer("❌ Урок не найден")
        await state.clear()
        return

    # Определяем тип медиа и получаем файл
    audio_file = None
    file_ext = None

    if message.audio:
        audio_file = message.audio
        file_ext = "mp3"
    elif message.voice:
        audio_file = message.voice
        file_ext = "ogg"
    elif message.document:
        audio_file = message.document

        # Определяем расширение из имени файла
        if audio_file.file_name:
            file_ext = audio_file.file_name.split('.')[-1].lower() if '.' in audio_file.file_name else "unknown"
        else:
            file_ext = "unknown"
    else:
        await message.answer(
            "❌ Пожалуйста, отправьте аудиофайл\n\n"
            "📋 Поддерживаемые форматы: MP3, WAV, FLAC, M4A, OGG, AAC и другие",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_lesson_{lesson.id}")
            ]])
        )
        return

    # Проверяем размер файла
    file_size_mb = audio_file.file_size / (1024 * 1024) if audio_file.file_size else 0
    logger.info(f"Получен новый аудиофайл для замены: урок_id={lesson_id}, размер={file_size_mb:.2f} МБ, расширение={file_ext}")

    if file_size_mb > config.max_audio_size_mb:
        logger.warning(f"Файл отклонён: {file_size_mb:.2f} МБ > {config.max_audio_size_mb} МБ")
        await message.answer(
            f"❌ Файл слишком большой ({file_size_mb:.1f} МБ)\n\n"
            f"📏 Максимальный размер: {config.max_audio_size_mb} МБ (лимит Telegram Bot API)\n\n"
            f"🌐 Для больших файлов используйте для конвертации:\n"
            f"{config.web_converter_url}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_lesson_{lesson.id}")
            ]])
        )
        await state.clear()
        return

    # Показываем сообщение о начале обработки
    processing_msg = await message.answer("⏳ Скачивание нового аудио файла...")

    # Скачиваем аудиофайл
    try:
        file_info = await message.bot.get_file(audio_file.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)
    except Exception as e:
        await processing_msg.edit_text(
            f"❌ Ошибка при скачивании файла: {str(e)}\n\n"
            f"Попробуйте отправить файл меньшего размера.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_lesson_{lesson.id}")
            ]])
        )
        await state.clear()
        return

    # Создаём директории для аудио
    original_dir = "bot/audio_files/original"
    converted_dir = "bot/audio_files/converted"
    os.makedirs(original_dir, exist_ok=True)
    os.makedirs(converted_dir, exist_ok=True)

    # Сохраняем оригинальный файл
    original_path = os.path.join(original_dir, f"{audio_file.file_unique_id}.{file_ext}")
    with open(original_path, "wb") as f:
        f.write(downloaded_file.getvalue())

    logger.info(f"Оригинальный файл сохранён: {original_path}")

    # Обновляем сообщение о процессе
    if file_size_mb > 100:
        time_estimate = "несколько минут"
    elif file_size_mb > 500:
        time_estimate = "5-10 минут"
    else:
        time_estimate = "несколько секунд"

    await processing_msg.edit_text(
        f"⏳ Обработка нового аудио файла...\n\n"
        f"📊 Исходный размер: {format_file_size(audio_file.file_size)}\n"
        f"⏱ Примерное время: {time_estimate}\n\n"
        f"Пожалуйста, подождите..."
    )

    # Получаем данные урока для генерации имени файла
    teacher = await get_lesson_teacher_by_id(lesson.teacher_id) if lesson.teacher_id else None
    book = await get_book_by_id(lesson.book_id) if lesson.book_id else None

    # Функция для очистки имени файла от недопустимых символов
    def sanitize_filename(name):
        """Удаляет недопустимые символы из имени файла"""
        if not name:
            return "unnamed"
        # Заменяем недопустимые символы на подчёркивание
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        # Убираем множественные пробелы и подчёркивания
        name = re.sub(r'[\s_]+', '_', name)
        # Ограничиваем длину
        return name[:50]

    # Формируем имя файла
    parts = []
    if teacher:
        parts.append(sanitize_filename(teacher.name))
    if book:
        parts.append(sanitize_filename(book.name))
    parts.append(f"{lesson.series_year}")
    parts.append(sanitize_filename(lesson.series_name))
    if lesson.lesson_number:
        parts.append(f"урок_{lesson.lesson_number}")

    new_filename = "_".join(parts) + ".mp3"
    converted_path = os.path.join(converted_dir, new_filename)

    # Конвертируем в MP3 с автоматическим подбором битрейта
    success, error, used_bitrate = await convert_to_mp3_auto(
        original_path,
        converted_path,
        preferred_bitrate=64  # Предпочтительный битрейт для хорошего качества
    )

    if not success:
        await processing_msg.edit_text(
            f"❌ Ошибка обработки аудио:\n\n{error}\n\n"
            "Попробуйте отправить файл в другом формате (MP3, WAV, FLAC) "
            "или разделите урок на части по 1-2 часа.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К редактированию урока", callback_data=f"edit_lesson_{lesson.id}")
            ]])
        )
        # Удаляем оригинальный файл при ошибке
        if os.path.exists(original_path):
            os.remove(original_path)
        if os.path.exists(converted_path):
            os.remove(converted_path)
        await state.clear()
        return

    # Получаем длительность автоматически
    duration_seconds = await get_audio_duration(converted_path)

    if not duration_seconds:
        logger.warning(f"Не удалось определить длительность для {converted_path}")
        duration_seconds = 0

    # Сохраняем путь к старому файлу (удалим только после успешного обновления БД)
    old_audio_path = None
    if lesson.audio_path:
        old_audio_path = os.path.join(config.audio_files_path, lesson.audio_path)

    # СНАЧАЛА обновляем урок в базе
    try:
        # Обновляем поля урока
        lesson.audio_path = converted_path
        lesson.duration_seconds = duration_seconds

        # Сохраняем изменения в БД
        await update_lesson(lesson)
        logger.info(f"База данных обновлена: урок {lesson.id}, новый файл: {converted_path}")

        # ТОЛЬКО ПОСЛЕ успешного обновления БД удаляем старый файл
        if old_audio_path and os.path.exists(old_audio_path):
            try:
                os.remove(old_audio_path)
                logger.info(f"Удалён старый аудиофайл: {old_audio_path}")
            except Exception as e:
                logger.error(f"Ошибка при удалении старого файла {old_audio_path}: {e}")
                # Это не критично - новый файл уже в БД, просто старый остался на диске

        # Удаляем сообщение о обработке
        await processing_msg.delete()

        # Получаем размеры файлов
        mp3_size = os.path.getsize(converted_path)
        original_size = os.path.getsize(original_path)

        # Показываем успешный результат
        success_message = (
            f"✅ <b>Аудиофайл успешно заменён!</b>\n\n"
            f"<b>Урок:</b> {lesson.title}\n\n"
            f"📊 Новая длительность: {format_duration(duration_seconds)}\n"
            f"🎵 Битрейт MP3: {used_bitrate} kbps\n"
            f"💾 Размер MP3: {format_file_size(mp3_size)}\n"
            f"📁 Оригинал: {format_file_size(original_size)}"
        )

        # Если был использован битрейт ниже предпочтительного, добавляем пояснение
        if used_bitrate and used_bitrate < 64:
            success_message += (
                f"\n\nℹ️ Битрейт автоматически снижен до {used_bitrate} kbps "
                f"для соблюдения лимита 50 МБ"
            )

        if old_audio_path:
            success_message += f"\n\n🗑 Старый файл удалён"

        await message.answer(
            success_message,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К редактированию урока", callback_data=f"edit_lesson_{lesson.id}")
            ]])
        )

        logger.info(f"Аудиофайл урока {lesson.id} заменён: {converted_path}, длительность: {duration_seconds}с")
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при обновлении урока: {str(e)}")
        await processing_msg.edit_text(
            f"❌ Ошибка при сохранении в базу данных:\n{str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К редактированию урока", callback_data=f"edit_lesson_{lesson.id}")
            ]])
        )
        # Удаляем новые файлы при ошибке
        if os.path.exists(original_path):
            os.remove(original_path)
        if os.path.exists(converted_path):
            os.remove(converted_path)
        await state.clear()
