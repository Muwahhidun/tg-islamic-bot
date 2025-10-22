"""
Обработчики для навигации по преподавателям (пользовательский интерфейс)
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.services.database_service import (
    LessonTeacherService,
    get_themes_by_teacher,
    get_books_by_teacher_and_theme,
    get_series_by_teacher_and_book,
    BookService,
)
from bot.keyboards.user import (
    get_teachers_keyboard,
    get_teacher_themes_keyboard,
    get_teacher_books_keyboard,
    get_teacher_series_keyboard,
)
from bot.utils.decorators import user_required_callback

router = Router()


@router.callback_query(F.data == "show_teachers")
@user_required_callback
async def show_teachers_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки 'Список преподавателей' - показывает список доступных преподавателей
    """
    # Очищаем состояние
    await state.clear()

    teachers = await LessonTeacherService.get_all_active_teachers()

    text = "👤 Выберите преподавателя:"
    keyboard = get_teachers_keyboard(teachers)

    if not teachers:
        text = "📭 Пока нет доступных преподавателей"

    await callback.message.edit_text(text, reply_markup=keyboard if teachers else None)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+$"))
@user_required_callback
async def show_teacher_themes(callback: CallbackQuery, state: FSMContext):
    """
    Показать список тем выбранного преподавателя
    """
    # Очищаем состояние
    await state.clear()

    teacher_id = int(callback.data.split("_")[1])
    teacher = await LessonTeacherService.get_teacher_by_id(teacher_id)

    if not teacher:
        await callback.answer("❌ Преподаватель не найден", show_alert=True)
        return

    themes = await get_themes_by_teacher(teacher_id)

    if not themes:
        await callback.answer("📭 У этого преподавателя пока нет доступных тем", show_alert=True)
        return

    text = f"🎙️ Преподаватель: {teacher.name}\n\nВыберите тему:"
    keyboard = get_teacher_themes_keyboard(themes, teacher_id)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_theme_\d+$"))
@user_required_callback
async def show_teacher_books(callback: CallbackQuery, state: FSMContext):
    """
    Показать книги преподавателя по выбранной теме
    """
    # Очищаем состояние
    await state.clear()

    parts = callback.data.split("_")
    teacher_id = int(parts[1])
    theme_id = int(parts[3])

    teacher = await LessonTeacherService.get_teacher_by_id(teacher_id)
    if not teacher:
        await callback.answer("❌ Преподаватель не найден", show_alert=True)
        return

    books = await get_books_by_teacher_and_theme(teacher_id, theme_id)

    if not books:
        await callback.answer("📭 У этого преподавателя нет книг по данной теме", show_alert=True)
        return

    # Формируем текст с темой
    theme_name = books[0].theme.name if books and books[0].theme else "Неизвестная тема"
    text = (
        f"🎙️ Преподаватель: {teacher.name}\n"
        f"📚 Тема: {theme_name}\n\n"
        f"Выберите книгу:"
    )
    keyboard = get_teacher_books_keyboard(books, teacher_id, theme_id)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_book_\d+$"))
@user_required_callback
async def show_teacher_series(callback: CallbackQuery, state: FSMContext):
    """
    Показать серии преподавателя по выбранной книге
    """
    # Очищаем состояние
    await state.clear()

    parts = callback.data.split("_")
    teacher_id = int(parts[1])
    book_id = int(parts[3])

    teacher = await LessonTeacherService.get_teacher_by_id(teacher_id)
    book = await BookService.get_book_by_id(book_id)

    if not teacher or not book:
        await callback.answer("❌ Данные не найдены", show_alert=True)
        return

    series_list = await get_series_by_teacher_and_book(teacher_id, book_id)

    if not series_list:
        await callback.answer("📭 У этого преподавателя нет серий по данной книге", show_alert=True)
        return

    text = (
        f"🎙️ Преподаватель: {teacher.name}\n"
        f"📚 Тема: {book.theme.name if book.theme else 'Без темы'}\n"
        f"📖 Книга: «{book.name}»\n"
        f"✍️ Автор книги: {book.author_info}\n\n"
        f"Выберите серию:"
    )
    keyboard = get_teacher_series_keyboard(series_list, teacher_id, book_id)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "back_to_teachers")
@user_required_callback
async def back_to_teachers_handler(callback: CallbackQuery, state: FSMContext):
    """
    Возврат к списку преподавателей
    """
    # Очищаем состояние
    await state.clear()

    teachers = await LessonTeacherService.get_all_active_teachers()

    text = "👤 Выберите преподавателя:"
    keyboard = get_teachers_keyboard(teachers)

    if not teachers:
        text = "📭 Пока нет доступных преподавателей"

    await callback.message.edit_text(text, reply_markup=keyboard if teachers else None)
    await callback.answer()
