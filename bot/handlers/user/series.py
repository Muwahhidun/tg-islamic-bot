"""
Обработчики для работы с сериями уроков (пользовательский интерфейс)
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.services.database_service import (
    BookService,
    get_series_by_book,
    get_series_by_id,
    get_test_by_series,
    LessonService
)
from bot.keyboards.user import get_series_keyboard, get_series_menu_keyboard, get_lessons_keyboard
from bot.utils.decorators import user_required_callback

router = Router()


@router.callback_query(F.data.regexp(r"^book_\d+$"))
@user_required_callback
async def show_book_teachers(callback: CallbackQuery, state: FSMContext):
    """
    Показать список преподавателей книги
    """
    # Очищаем состояние
    await state.clear()

    book_id = int(callback.data.split("_")[1])
    book = await BookService.get_book_by_id(book_id)

    if not book:
        await callback.answer("📖 Книга не найдена", show_alert=True)
        return

    # Получаем серии этой книги
    series_list = await get_series_by_book(book_id)

    if not series_list:
        await callback.answer("📭 В этой книге пока нет уроков", show_alert=True)
        return

    # Получаем уникальных преподавателей этой книги
    teachers = {}
    for series in series_list:
        if series.teacher_id and series.teacher:
            if series.teacher_id not in teachers:
                teachers[series.teacher_id] = series.teacher

    if not teachers:
        await callback.answer("📭 В этой книге пока нет преподавателей", show_alert=True)
        return

    # Сохраняем book_id для навигации назад
    await state.update_data(current_book_id=book_id)

    text = ""
    if book.theme:
        text += f"📚 Тема: {book.theme.name}\n"
    text += (
        f"📖 Книга: «{book.name}»\n"
        f"✍️ Автор: {book.author_info}\n\n"
        f"🎙️ Выберите преподавателя ({len(teachers)}):"
    )

    # Создаём клавиатуру с преподавателями
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard_buttons = []
    for teacher in teachers.values():
        keyboard_buttons.append([InlineKeyboardButton(
            text=f"🎙️ {teacher.name}",
            callback_data=f"book_teacher_{book_id}_{teacher.id}"
        )])

    # Кнопка назад к книгам темы
    keyboard_buttons.append([InlineKeyboardButton(
        text="⬅️ Назад к книгам",
        callback_data=f"theme_{book.theme_id}"
    )])
    keyboard_buttons.append([InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="main_menu"
    )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("book_teacher_"))
@user_required_callback
async def show_teacher_series_for_book(callback: CallbackQuery, state: FSMContext):
    """
    Показать серии конкретного преподавателя по выбранной книге
    """
    # Очищаем состояние
    await state.clear()

    parts = callback.data.split("_")
    book_id = int(parts[2])
    teacher_id = int(parts[3])

    book = await BookService.get_book_by_id(book_id)
    from bot.services.database_service import get_lesson_teacher_by_id
    teacher = await get_lesson_teacher_by_id(teacher_id)

    if not book or not teacher:
        await callback.answer("❌ Данные не найдены", show_alert=True)
        return

    # Получаем серии этого преподавателя для этой книги
    series_list = await get_series_by_book(book_id)
    teacher_series = [s for s in series_list if s.teacher_id == teacher_id]

    if not teacher_series:
        await callback.answer("📭 У этого преподавателя пока нет серий по этой книге", show_alert=True)
        return

    # Сохраняем данные для навигации назад
    await state.update_data(current_book_id=book_id, current_teacher_id=teacher_id)

    text = ""
    if book.theme:
        text += f"📚 Тема: {book.theme.name}\n"
    text += f"📖 Книга: «{book.name}»\n"
    text += f"✍️ Автор: {book.author_info}\n"
    text += (
        f"🎙️ Преподаватель: {teacher.name}\n\n"
        f"📁 Выберите серию уроков ({len(teacher_series)}):"
    )

    # Создаём клавиатуру с сериями
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard_buttons = []
    for series in teacher_series:
        lessons_count = series.active_lessons_count
        text_button = f"📁 {series.year} - {series.name} ({lessons_count} уроков)"
        keyboard_buttons.append([InlineKeyboardButton(
            text=text_button,
            callback_data=f"series_{series.id}"
        )])

    # Кнопка назад к преподавателям
    keyboard_buttons.append([InlineKeyboardButton(
        text="⬅️ Назад к преподавателям",
        callback_data=f"book_{book_id}"
    )])
    keyboard_buttons.append([InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="main_menu"
    )])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("series_") & ~F.data.startswith("series_lessons_"))
@user_required_callback
async def show_series_menu(callback: CallbackQuery, state: FSMContext):
    """
    Показать меню серии (Уроки / Общий тест / Назад)
    """
    # Очищаем состояние
    await state.clear()

    series_id = int(callback.data.split("_")[1])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("📁 Серия не найдена", show_alert=True)
        return

    # Сохраняем series_id, book_id и teacher_id для навигации
    await state.update_data(
        current_series_id=series_id,
        current_book_id=series.book_id,
        current_teacher_id=series.teacher_id
    )

    # Проверяем, есть ли тест для этой серии
    test = await get_test_by_series(series_id)
    has_test = test is not None and test.is_active

    # Формируем информацию о серии
    text = ""

    # Получаем информацию о книге для отображения темы и автора
    from bot.services.database_service import get_book_by_id
    book = None
    if series.book_id:
        book = await get_book_by_id(series.book_id)

    # Тема
    if book and book.theme:
        text += f"📚 Тема: {book.theme.name}\n"

    # Книга
    text += f"📖 Книга: «{series.book_title or 'Не указана'}»\n"

    # Автор книги
    if book and book.author:
        text += f"✍️ Автор: {book.author_info}\n"

    # Преподаватель
    text += f"🎙️ Преподаватель: {series.teacher_name}\n"

    # Название серии
    text += f"📁 Серия: {series.display_name}\n"

    # Статистика
    text += f"🎧 Уроков: {series.active_lessons_count}\n"

    if series.total_duration_seconds > 0:
        text += f"⏱️ Длительность: {series.formatted_total_duration}\n"

    if series.is_completed:
        text += "✅ Серия завершена\n"
    else:
        text += "🔄 В процессе\n"

    if series.description:
        text += f"\n📄 {series.description}\n"

    text += "\n<b>Выберите действие:</b>"

    keyboard = get_series_menu_keyboard(series_id, has_test)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("series_lessons_"))
@user_required_callback
async def show_series_lessons(callback: CallbackQuery, state: FSMContext):
    """
    Показать список уроков серии с кнопками тестов
    """
    series_id = int(callback.data.split("_")[2])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("📁 Серия не найдена", show_alert=True)
        return

    # Получаем уроки этой серии
    lessons = await LessonService.get_lessons_by_series(series_id)

    if not lessons:
        await callback.answer("📭 В этой серии пока нет уроков", show_alert=True)
        return

    # Сохраняем series_id для навигации
    await state.update_data(current_series_id=series_id)

    # TODO: Проверить, есть ли тесты для каждого урока
    # Пока передаем пустой словарь, позже добавим проверку
    has_tests = {}

    # Формируем текст с полной иерархией
    text = ""

    # Получаем информацию о книге для отображения темы и автора
    from bot.services.database_service import get_book_by_id
    book = None
    if series.book_id:
        book = await get_book_by_id(series.book_id)

    # Тема
    if book and book.theme:
        text += f"📚 Тема: {book.theme.name}\n"

    # Книга
    text += f"📖 Книга: «{series.book_title or 'Не указана'}»\n"

    # Автор книги
    if book and book.author:
        text += f"✍️ Автор: {book.author_info}\n"

    # Преподаватель
    text += f"🎙️ Преподаватель: {series.teacher_name}\n"

    # Серия
    text += f"📁 Серия: {series.display_name}\n"

    # Длительность
    if series.total_duration_seconds > 0:
        text += f"⏱️ Длительность: {series.formatted_total_duration}\n"

    # Статус
    if series.is_completed:
        text += "✅ Серия завершена\n"
    else:
        text += "🔄 В процессе\n"

    text += f"\n🎧 Список уроков ({len(lessons)}):"

    keyboard = get_lessons_keyboard(lessons, series_id, has_tests)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("back_to_series_lessons_"))
@user_required_callback
async def back_to_series_lessons(callback: CallbackQuery, state: FSMContext):
    """
    Вернуться к списку уроков серии
    """
    series_id = int(callback.data.split("_")[4])

    # Получаем серию и уроки напрямую
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("📁 Серия не найдена", show_alert=True)
        return

    lessons = await LessonService.get_lessons_by_series(series_id)

    if not lessons:
        await callback.answer("📭 В этой серии пока нет уроков", show_alert=True)
        return

    await state.update_data(current_series_id=series_id)

    # TODO: Проверить наличие тестов для каждого урока
    has_tests = {}

    # Формируем текст с полной иерархией
    text = ""

    # Получаем информацию о книге для отображения темы и автора
    from bot.services.database_service import get_book_by_id
    book = None
    if series.book_id:
        book = await get_book_by_id(series.book_id)

    # Тема
    if book and book.theme:
        text += f"📚 Тема: {book.theme.name}\n"

    # Книга
    text += f"📖 Книга: «{series.book_title or 'Не указана'}»\n"

    # Автор книги
    if book and book.author:
        text += f"✍️ Автор: {book.author_info}\n"

    # Преподаватель
    text += f"🎙️ Преподаватель: {series.teacher_name}\n"

    # Серия
    text += f"📁 Серия: {series.display_name}\n"

    # Длительность
    if series.total_duration_seconds > 0:
        text += f"⏱️ Длительность: {series.formatted_total_duration}\n"

    # Статус
    if series.is_completed:
        text += "✅ Серия завершена\n"
    else:
        text += "🔄 В процессе\n"

    text += f"\n🎧 Список уроков ({len(lessons)}):"

    keyboard = get_lessons_keyboard(lessons, series_id, has_tests)

    # Если сообщение содержит аудио (нельзя edit_text), удаляем его и отправляем текстовое
    if callback.message.audio:
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(text, reply_markup=keyboard)
    else:
        # Если текстовое сообщение, редактируем
        await callback.message.edit_text(text, reply_markup=keyboard)

    await callback.answer()


@router.callback_query(F.data == "back_to_series_list")
@user_required_callback
async def back_to_series_list(callback: CallbackQuery, state: FSMContext):
    """
    Вернуться к списку серий преподавателя для книги
    """
    data = await state.get_data()
    book_id = data.get("current_book_id")
    teacher_id = data.get("current_teacher_id")

    if not book_id or not teacher_id:
        await callback.answer("Ошибка навигации", show_alert=True)
        return

    # Перенаправляем на обработчик показа серий преподавателя
    from copy import copy
    new_callback = copy(callback)
    object.__setattr__(new_callback, 'data', f"book_teacher_{book_id}_{teacher_id}")
    await show_teacher_series_for_book(new_callback, state)
