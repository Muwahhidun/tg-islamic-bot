"""
Обработчики управления уроками для администраторов
"""
import os

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required
from bot.services.database_service import (
    get_all_lessons,
    get_all_books,
    get_all_themes,
    get_all_lesson_teachers,
    get_lesson_by_id,
    create_lesson
)
from bot.models.lesson import Lesson
from bot.models.book import Book
from bot.models.database import async_session_maker
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload, joinedload

router = Router()


class LessonStates(StatesGroup):
    """Состояния для управления уроками"""
    title = State()
    description = State()
    series_year = State()
    series_name = State()
    book_id = State()
    teacher_id = State()
    lesson_number = State()
    duration_minutes = State()
    tags = State()
    audio_file = State()


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
            text=f"👨‍🏫 {teacher.name} ({teacher_lessons_count} урок.)",
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

    # Фильтруем темы, у которых есть книги с уроками данного преподавателя
    async with async_session_maker() as session:
        session.expire_on_commit = False
        result = await session.execute(
            select(Lesson)
            .where(Lesson.teacher_id == teacher_id)
            .options(joinedload(Lesson.book).joinedload(Book.theme))
        )
        teacher_lessons = result.scalars().unique().all()

    # Получаем уникальные темы через книги и собираем данные
    theme_data = {}
    for lesson in teacher_lessons:
        if lesson.book and lesson.book.theme:
            theme_id = lesson.book.theme.id
            if theme_id not in theme_data:
                theme_data[theme_id] = {
                    "id": theme_id,
                    "name": lesson.book.theme.name,
                    "count": 0
                }
            theme_data[theme_id]["count"] += 1

    if not theme_data:
        await callback.message.edit_text(
            "❌ У этого преподавателя пока нет уроков",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data="admin_lessons")
            ]])
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
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


@router.callback_query(F.data.regexp(r"^lessons_theme_\d+_\d+$"))
@admin_required
async def show_theme_books(callback: CallbackQuery):
    """Показать книги в выбранной теме для данного преподавателя"""
    parts = callback.data.split("_")
    teacher_id = int(parts[2])
    theme_id = int(parts[3])

    # Получаем уроки преподавателя в данной теме
    async with async_session_maker() as session:
        result = await session.execute(
            select(Lesson)
            .where(Lesson.teacher_id == teacher_id)
            .options(selectinload(Lesson.book).selectinload(Book.theme))
        )
        teacher_lessons = result.scalars().all()

        # Фильтруем книги по теме и собираем данные внутри сессии
        book_data = {}
        theme_name = None
        for lesson in teacher_lessons:
            if lesson.book and lesson.book.theme_id == theme_id:
                if theme_name is None and lesson.book.theme:
                    theme_name = lesson.book.theme.name

                book_id = lesson.book.id
                if book_id not in book_data:
                    book_data[book_id] = {
                        "id": book_id,
                        "name": lesson.book.name,
                        "count": 0
                    }
                book_data[book_id]["count"] += 1

    if not book_data:
        await callback.message.edit_text(
            "❌ В этой теме пока нет книг с уроками данного преподавателя",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"lessons_teacher_{teacher_id}")
            ]])
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
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
    builder.adjust(1)

    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Выберите книгу для урока:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(LessonStates.book_id)


@router.callback_query(F.data.startswith("select_book_"))
@admin_required
async def select_book_for_lesson(callback: CallbackQuery, state: FSMContext):
    """Выбрать книгу для урока"""
    book_id = int(callback.data.split("_")[2])
    await state.update_data(book_id=book_id)

    # Получаем список преподавателей
    teachers = await get_all_lesson_teachers()

    builder = InlineKeyboardBuilder()
    for teacher in teachers:
        builder.add(InlineKeyboardButton(text=teacher.name, callback_data=f"select_teacher_{teacher.id}"))

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
            "Введите длительность урока в минутах:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )
        await state.set_state(LessonStates.duration_minutes)
    except ValueError:
        await message.answer(
            "❌ Номер урока должен быть числом. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )


@router.message(LessonStates.duration_minutes)
@admin_required
async def add_lesson_duration(message: Message, state: FSMContext):
    """Сохранить длительность урока"""
    try:
        duration_minutes = int(message.text)
        await state.update_data(duration_minutes=duration_minutes)

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
            "❌ Длительность должна быть числом. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )


@router.callback_query(F.data == "skip_lesson_tags")
@admin_required
async def add_lesson_skip_tags(callback: CallbackQuery, state: FSMContext):
    """Пропустить теги урока"""
    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Отправьте аудиофайл урока:",
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
        "Отправьте аудиофайл урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.audio_file)


@router.message(LessonStates.audio_file)
@admin_required
async def add_lesson_audio(message: Message, state: FSMContext):
    """Сохранить аудиофайл урока"""
    data = await state.get_data()

    # Список поддерживаемых форматов
    SUPPORTED_FORMATS = ['mp3', 'm4a', 'ogg', 'oga']
    SUPPORTED_MIME_TYPES = [
        'audio/mpeg', 'audio/mp3',           # MP3
        'audio/mp4', 'audio/x-m4a', 'audio/m4a',  # M4A
        'audio/ogg', 'audio/opus', 'audio/vorbis'  # OGG
    ]

    # Определяем тип медиа и получаем файл
    if message.audio:
        audio_file = message.audio
        file_ext = "mp3"
    elif message.voice:
        audio_file = message.voice
        file_ext = "ogg"
    elif message.document:
        audio_file = message.document

        # Проверяем MIME-тип
        if audio_file.mime_type and not audio_file.mime_type.startswith('audio/'):
            await message.answer(
                "❌ Это не аудиофайл!\n\n"
                "📋 Поддерживаемые форматы:\n"
                "• MP3 (рекомендуется)\n"
                "• M4A\n"
                "• OGG\n\n"
                "Пожалуйста, отправьте аудиофайл в одном из этих форматов.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")
                ]])
            )
            return

        # Определяем расширение из mime_type или имени файла
        if audio_file.file_name:
            file_ext = audio_file.file_name.split('.')[-1].lower() if '.' in audio_file.file_name else "mp3"
        elif audio_file.mime_type:
            mime_to_ext = {
                "audio/mpeg": "mp3", "audio/mp3": "mp3",
                "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/m4a": "m4a",
                "audio/ogg": "ogg", "audio/opus": "ogg", "audio/vorbis": "ogg"
            }
            file_ext = mime_to_ext.get(audio_file.mime_type, "mp3")
        else:
            file_ext = "mp3"

        # Проверяем поддерживаемый формат
        if file_ext not in SUPPORTED_FORMATS:
            await message.answer(
                f"❌ Формат .{file_ext.upper()} не поддерживается!\n\n"
                "📋 Поддерживаемые форматы:\n"
                "• MP3 (рекомендуется) ✅\n"
                "• M4A ✅\n"
                "• OGG ✅\n\n"
                f"Ваш файл: .{file_ext.upper()}\n\n"
                "Пожалуйста, конвертируйте файл в MP3 или M4A и отправьте снова.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")
                ]])
            )
            return
    else:
        await message.answer(
            "❌ Пожалуйста, отправьте аудиофайл\n\n"
            "📋 Поддерживаемые форматы:\n"
            "• MP3 (рекомендуется)\n"
            "• M4A\n"
            "• OGG"
        )
        return

    # Проверяем размер файла (максимум 20 МБ = 20 * 1024 * 1024 байт)
    file_size_mb = audio_file.file_size / (1024 * 1024) if audio_file.file_size else 0
    if file_size_mb > 20:
        await message.answer(
            f"❌ Файл слишком большой ({file_size_mb:.1f} МБ)\n\n"
            f"Максимальный размер: 20 МБ\n"
            f"Пожалуйста, сожмите аудио или отправьте файл меньшего размера.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")
            ]])
        )
        await state.clear()
        return

    # Скачиваем аудиофайл
    try:
        file_info = await message.bot.get_file(audio_file.file_id)
        downloaded_file = await message.bot.download_file(file_info.file_path)
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при скачивании файла: {str(e)}\n\n"
            f"Попробуйте отправить файл меньшего размера.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")
            ]])
        )
        await state.clear()
        return

    # Сохраняем файл
    audio_dir = "bot/audio_files"
    os.makedirs(audio_dir, exist_ok=True)

    file_path = os.path.join(audio_dir, f"{audio_file.file_unique_id}.{file_ext}")
    with open(file_path, "wb") as f:
        f.write(downloaded_file.getvalue())

    lesson = await create_lesson(
        title=data["title"],
        series_year=data["series_year"],
        series_name=data["series_name"],
        description=data.get("description", ""),
        audio_file_path=file_path,
        duration_minutes=data["duration_minutes"],
        lesson_number=data["lesson_number"],
        book_id=data["book_id"],
        teacher_id=data["teacher_id"],
        tags=data.get("tags", ""),
        is_active=True
    )

    await message.answer(
        f"✅ Урок «{lesson.title}» успешно добавлен!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку уроков", callback_data="admin_lessons")]])
    )
    await state.clear()


@router.callback_query(F.data.startswith("edit_lesson_"))
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
    info += f"📖 Книга: {lesson.book_title}\n"
    info += f"👨‍🏫 Преподаватель: {lesson.teacher_name}\n"

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
    builder.add(InlineKeyboardButton(text="✏️ Изменить год серии", callback_data=f"edit_lesson_year_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Изменить название серии", callback_data=f"edit_lesson_series_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Изменить номер урока", callback_data=f"edit_lesson_number_{lesson.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Изменить теги", callback_data=f"edit_lesson_tags_{lesson.id}"))

    if lesson.is_active:
        builder.add(InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"toggle_lesson_active_{lesson.id}"))
    else:
        builder.add(InlineKeyboardButton(text="✅ Активировать", callback_data=f"toggle_lesson_active_{lesson.id}"))

    builder.add(InlineKeyboardButton(text="🗑 Удалить урок", callback_data=f"delete_lesson_{lesson.id}"))

    # Кнопка назад к списку уроков серии
    theme_id = lesson.theme_id if lesson.theme_id else 0
    back_callback = f"lessons_series_{lesson.teacher_id}_{theme_id}_{lesson.book_id}_{lesson.series_year}_{lesson.series_name}"
    builder.add(InlineKeyboardButton(text="🔙 К списку уроков", callback_data=back_callback))
    builder.adjust(1)

    await callback.message.edit_text(
        info,
        reply_markup=builder.as_markup()
    )
    await callback.answer()
