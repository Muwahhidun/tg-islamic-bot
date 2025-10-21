"""
Управление сериями уроков преподавателей
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, distinct, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.utils.decorators import admin_required
from bot.services.database_service import (
    get_lesson_teacher_by_id,
    get_all_lessons,
    get_all_books,
)
from bot.models.lesson import Lesson
from bot.models.database import async_session_maker
from bot.handlers.admin.teachers import LessonTeacherStates

router = Router()


@router.callback_query(F.data.startswith("manage_teacher_series_"))
@admin_required
async def manage_teacher_series(callback: CallbackQuery):
    """Показать список книг преподавателя для управления сериями"""
    teacher_id = int(callback.data.split("_")[3])
    teacher = await get_lesson_teacher_by_id(teacher_id)

    if not teacher:
        await callback.answer("❌ Преподаватель не найден", show_alert=True)
        return

    # Получаем все уроки преподавателя
    all_lessons = await get_all_lessons()
    teacher_lessons = [l for l in all_lessons if l.teacher_id == teacher_id]

    if not teacher_lessons:
        await callback.message.edit_text(
            f"📁 <b>Управление сериями</b>\n\n"
            f"Преподаватель: {teacher.name}\n\n"
            f"У этого преподавателя пока нет уроков.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"edit_teacher_{teacher_id}")
            ]])
        )
        await callback.answer()
        return

    # Получаем уникальные книги
    book_ids = list(set([l.book_id for l in teacher_lessons if l.book_id]))
    books = await get_all_books()
    teacher_books = [b for b in books if b.id in book_ids]

    builder = InlineKeyboardBuilder()
    for book in teacher_books:
        builder.add(InlineKeyboardButton(
            text=f"📖 {book.name}",
            callback_data=f"teacher_series_book_{teacher_id}_{book.id}"
        ))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"edit_teacher_{teacher_id}"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"📁 <b>Управление сериями</b>\n\n"
        f"Преподаватель: {teacher.name}\n\n"
        f"Выберите книгу:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_series_book_\d+_\d+$"))
@admin_required
async def show_series_list(callback: CallbackQuery):
    """Показать список серий по выбранной книге"""
    parts = callback.data.split("_")
    teacher_id = int(parts[3])
    book_id = int(parts[4])

    teacher = await get_lesson_teacher_by_id(teacher_id)
    books = await get_all_books()
    book = next((b for b in books if b.id == book_id), None)

    if not teacher or not book:
        await callback.answer("❌ Данные не найдены", show_alert=True)
        return

    # Получаем уникальные серии для этой книги и преподавателя
    async with async_session_maker() as session:
        result = await session.execute(
            select(distinct(Lesson.series_year), distinct(Lesson.series_name))
            .where(Lesson.teacher_id == teacher_id, Lesson.book_id == book_id)
            .order_by(Lesson.series_year.desc(), Lesson.series_name)
        )
        series_data = result.all()

    if not series_data:
        await callback.message.edit_text(
            f"📁 <b>Управление сериями</b>\n\n"
            f"Преподаватель: {teacher.name}\n"
            f"Книга: {book.name}\n\n"
            f"Нет серий для этой книги.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"manage_teacher_series_{teacher_id}")
            ]])
        )
        await callback.answer()
        return

    # Группируем серии правильно
    async with async_session_maker() as session:
        result = await session.execute(
            select(Lesson.series_year, Lesson.series_name)
            .where(Lesson.teacher_id == teacher_id, Lesson.book_id == book_id)
            .group_by(Lesson.series_year, Lesson.series_name)
            .order_by(Lesson.series_year.desc(), Lesson.series_name)
        )
        series_list = result.all()

    builder = InlineKeyboardBuilder()
    for year, name in series_list:
        # Подсчитываем количество уроков в серии
        async with async_session_maker() as session:
            count_result = await session.execute(
                select(Lesson.id)
                .where(
                    Lesson.teacher_id == teacher_id,
                    Lesson.book_id == book_id,
                    Lesson.series_year == year,
                    Lesson.series_name == name
                )
            )
            lessons_count = len(count_result.all())

        builder.add(InlineKeyboardButton(
            text=f"📚 {year} - {name} ({lessons_count} урок.)",
            callback_data=f"edit_series_{teacher_id}_{book_id}_{year}_{name}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"manage_teacher_series_{teacher_id}"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"📁 <b>Управление сериями</b>\n\n"
        f"Преподаватель: {teacher.name}\n"
        f"Книга: {book.name}\n\n"
        f"Выберите серию для редактирования:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^edit_series_\d+_\d+_\d+_.+$"))
@admin_required
async def edit_series_menu(callback: CallbackQuery):
    """Меню редактирования серии"""
    parts = callback.data.split("_", 4)
    teacher_id = int(parts[2])
    book_id = int(parts[3])
    year = int(parts[4].split("_")[0])
    name = "_".join(parts[4].split("_")[1:])

    teacher = await get_lesson_teacher_by_id(teacher_id)
    books = await get_all_books()
    book = next((b for b in books if b.id == book_id), None)

    if not teacher or not book:
        await callback.answer("❌ Данные не найдены", show_alert=True)
        return

    # Подсчитываем количество уроков
    async with async_session_maker() as session:
        count_result = await session.execute(
            select(Lesson.id)
            .where(
                Lesson.teacher_id == teacher_id,
                Lesson.book_id == book_id,
                Lesson.series_year == year,
                Lesson.series_name == name
            )
        )
        lessons_count = len(count_result.all())

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="📅 Изменить год",
        callback_data=f"edit_series_year_{teacher_id}_{book_id}_{year}_{name}"
    ))
    builder.add(InlineKeyboardButton(
        text="✏️ Изменить название",
        callback_data=f"edit_series_name_{teacher_id}_{book_id}_{year}_{name}"
    ))
    builder.add(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data=f"teacher_series_book_{teacher_id}_{book_id}"
    ))
    builder.adjust(1)

    await callback.message.edit_text(
        f"📁 <b>Редактирование серии</b>\n\n"
        f"Преподаватель: {teacher.name}\n"
        f"Книга: {book.name}\n"
        f"Серия: {year} - {name}\n"
        f"Количество уроков: {lessons_count}\n\n"
        f"Выберите действие:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^edit_series_year_\d+_\d+_\d+_.+$"))
@admin_required
async def edit_series_year_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение года серии"""
    parts = callback.data.split("_", 5)
    teacher_id = int(parts[3])
    book_id = int(parts[4])
    old_year = int(parts[5].split("_")[0])
    old_name = "_".join(parts[5].split("_")[1:])

    await state.update_data(
        teacher_id=teacher_id,
        book_id=book_id,
        old_year=old_year,
        old_name=old_name
    )

    await callback.message.edit_text(
        f"📅 <b>Изменение года серии</b>\n\n"
        f"Текущий год: {old_year}\n\n"
        f"Введите новый год (2000-2050):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_series_{teacher_id}_{book_id}_{old_year}_{old_name}")
        ]])
    )
    await state.set_state(LessonTeacherStates.edit_series_year)
    await callback.answer()


@router.message(LessonTeacherStates.edit_series_year)
@admin_required
async def edit_series_year_save(message: Message, state: FSMContext):
    """Сохранить новый год серии"""
    try:
        new_year = int(message.text)
        if new_year < 2000 or new_year > 2050:
            await message.answer(
                "❌ Год должен быть в диапазоне 2000-2050. Попробуйте еще раз:"
            )
            return

        data = await state.get_data()
        teacher_id = data["teacher_id"]
        book_id = data["book_id"]
        old_year = data["old_year"]
        old_name = data["old_name"]

        # Обновляем год у всех уроков этой серии
        async with async_session_maker() as session:
            await session.execute(
                update(Lesson)
                .where(
                    Lesson.teacher_id == teacher_id,
                    Lesson.book_id == book_id,
                    Lesson.series_year == old_year,
                    Lesson.series_name == old_name
                )
                .values(series_year=new_year)
            )
            await session.commit()

        await message.answer(
            f"✅ Год серии изменен с {old_year} на {new_year}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К серии", callback_data=f"edit_series_{teacher_id}_{book_id}_{new_year}_{old_name}")
            ]])
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Год должен быть числом. Попробуйте еще раз:")


@router.callback_query(F.data.regexp(r"^edit_series_name_\d+_\d+_\d+_.+$"))
@admin_required
async def edit_series_name_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение названия серии"""
    parts = callback.data.split("_", 5)
    teacher_id = int(parts[3])
    book_id = int(parts[4])
    year = int(parts[5].split("_")[0])
    old_name = "_".join(parts[5].split("_")[1:])

    await state.update_data(
        teacher_id=teacher_id,
        book_id=book_id,
        year=year,
        old_name=old_name
    )

    await callback.message.edit_text(
        f"✏️ <b>Изменение названия серии</b>\n\n"
        f"Текущее название: {old_name}\n\n"
        f"Введите новое название:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_series_{teacher_id}_{book_id}_{year}_{old_name}")
        ]])
    )
    await state.set_state(LessonTeacherStates.edit_series_name)
    await callback.answer()


@router.message(LessonTeacherStates.edit_series_name)
@admin_required
async def edit_series_name_save(message: Message, state: FSMContext):
    """Сохранить новое название серии"""
    new_name = message.text
    data = await state.get_data()
    teacher_id = data["teacher_id"]
    book_id = data["book_id"]
    year = data["year"]
    old_name = data["old_name"]

    # Обновляем название у всех уроков этой серии
    async with async_session_maker() as session:
        await session.execute(
            update(Lesson)
            .where(
                Lesson.teacher_id == teacher_id,
                Lesson.book_id == book_id,
                Lesson.series_year == year,
                Lesson.series_name == old_name
            )
            .values(series_name=new_name)
        )
        await session.commit()

    await message.answer(
        f"✅ Название серии изменено с «{old_name}» на «{new_name}»",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 К серии", callback_data=f"edit_series_{teacher_id}_{book_id}_{year}_{new_name}")
        ]])
    )
    await state.clear()
