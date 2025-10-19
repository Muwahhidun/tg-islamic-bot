"""
Обработчики управления сериями уроков для администраторов
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required
from bot.services.database_service import (
    get_all_lesson_teachers,
    get_all_lesson_series,
    get_series_by_teacher,
    get_series_by_id,
    create_lesson_series,
    update_lesson_series,
    delete_lesson_series,
    get_all_books,
    get_all_themes,
    bulk_update_series_lessons,
    bulk_update_book_lessons,
    update_book
)

router = Router()


class SeriesStates(StatesGroup):
    """Состояния для управления сериями"""
    select_teacher = State()
    select_series = State()
    edit_name = State()
    edit_year = State()
    edit_description = State()
    select_book = State()
    select_theme = State()
    confirm_delete = State()


@router.callback_query(F.data == "admin_series")
@admin_required
async def series_menu(callback: CallbackQuery):
    """Главное меню управления сериями"""
    text = (
        "📚 <b>Управление сериями уроков</b>\n\n"
        "Выберите действие:"
    )

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📋 Список всех серий", callback_data="series_list_all"))
    builder.add(InlineKeyboardButton(text="👤 По преподавателям", callback_data="series_by_teacher"))
    builder.add(InlineKeyboardButton(text="➕ Создать новую серию", callback_data="series_create"))
    builder.add(InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_panel"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "series_list_all")
@admin_required
async def list_all_series(callback: CallbackQuery):
    """Показать список всех серий"""
    series_list = await get_all_lesson_series()

    if not series_list:
        await callback.answer("Пока нет ни одной серии", show_alert=True)
        return

    text = f"📚 <b>Все серии уроков</b>\n\nВсего серий: {len(series_list)}\n\n"

    builder = InlineKeyboardBuilder()
    for series in series_list:
        status = "✅" if series.is_completed else "🔄"
        active = "✅" if series.is_active else "❌"

        button_text = f"{status} {series.year} - {series.name} ({series.teacher_name}) {active}"
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"series_view_{series.id}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_series"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "series_by_teacher")
@admin_required
async def select_teacher_for_series(callback: CallbackQuery, state: FSMContext):
    """Выбор преподавателя для просмотра его серий"""
    teachers = await get_all_lesson_teachers()

    if not teachers:
        await callback.answer("Нет преподавателей", show_alert=True)
        return

    text = "👤 <b>Выберите преподавателя:</b>"

    builder = InlineKeyboardBuilder()
    for teacher in teachers:
        builder.add(InlineKeyboardButton(
            text=teacher.name,
            callback_data=f"series_teacher_{teacher.id}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_series"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("series_teacher_"))
@admin_required
async def show_teacher_series(callback: CallbackQuery):
    """Показать все серии преподавателя"""
    teacher_id = int(callback.data.split("_")[2])
    series_list = await get_series_by_teacher(teacher_id)

    if not series_list:
        await callback.answer("У преподавателя пока нет серий", show_alert=True)
        return

    teacher_name = series_list[0].teacher_name if series_list else "Преподаватель"

    text = f"📚 <b>Серии преподавателя {teacher_name}</b>\n\n"

    builder = InlineKeyboardBuilder()
    for series in series_list:
        lessons_count = series.total_lessons
        status = "✅" if series.is_completed else "🔄"
        active = "✅" if series.is_active else "❌"

        button_text = f"{status} {series.year} - {series.name} ({lessons_count} ур.) {active}"
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"series_view_{series.id}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Создать новую серию", callback_data=f"series_create_teacher_{teacher_id}"))
    builder.add(InlineKeyboardButton(text="🔙 К выбору преподавателя", callback_data="series_by_teacher"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("series_view_"))
@admin_required
async def view_series(callback: CallbackQuery):
    """Просмотр детальной информации о серии"""
    series_id = int(callback.data.split("_")[2])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        return

    text = series.full_info

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"series_edit_name_{series.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Редактировать год", callback_data=f"series_edit_year_{series.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Редактировать описание", callback_data=f"series_edit_desc_{series.id}"))
    builder.add(InlineKeyboardButton(text="📖 Изменить книгу", callback_data=f"series_edit_book_{series.id}"))

    # Всегда показываем кнопку "Изменить тему" - логика внутри обработчика
    builder.add(InlineKeyboardButton(text="📑 Изменить тему", callback_data=f"series_edit_theme_{series.id}"))

    if series.is_completed:
        builder.add(InlineKeyboardButton(text="🔄 Отметить как незавершённую", callback_data=f"series_toggle_completed_{series.id}"))
    else:
        builder.add(InlineKeyboardButton(text="✅ Отметить как завершённую", callback_data=f"series_toggle_completed_{series.id}"))

    if series.is_active:
        builder.add(InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"series_toggle_active_{series.id}"))
    else:
        builder.add(InlineKeyboardButton(text="✅ Активировать", callback_data=f"series_toggle_active_{series.id}"))

    builder.add(InlineKeyboardButton(text="🗑 Удалить серию", callback_data=f"series_delete_{series.id}"))
    builder.add(InlineKeyboardButton(text="🔙 К списку серий", callback_data=f"series_teacher_{series.teacher_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("series_edit_name_"))
@admin_required
async def edit_series_name(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование названия серии"""
    series_id = int(callback.data.split("_")[3])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        return

    await state.update_data(series_id=series_id)
    await state.set_state(SeriesStates.edit_name)

    await callback.message.edit_text(
        f"✏️ <b>Редактирование названия серии</b>\n\n"
        f"Текущее название: <b>{series.name}</b>\n\n"
        f"Введите новое название:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_view_{series_id}")
        ]])
    )
    await callback.answer()


@router.message(SeriesStates.edit_name)
@admin_required
async def save_series_name(message: Message, state: FSMContext):
    """Сохранить новое название серии"""
    data = await state.get_data()
    series_id = data.get("series_id")

    series = await get_series_by_id(series_id)
    if not series:
        await message.answer("❌ Серия не найдена")
        await state.clear()
        return

    series.name = message.text
    await update_lesson_series(series)

    await state.clear()
    await message.answer(
        f"✅ Название серии обновлено: <b>{series.name}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 К серии", callback_data=f"series_view_{series_id}")
        ]])
    )


@router.callback_query(F.data.startswith("series_toggle_completed_"))
@admin_required
async def toggle_series_completed(callback: CallbackQuery):
    """Переключить статус завершённости серии"""
    series_id = int(callback.data.split("_")[3])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        return

    series.is_completed = not series.is_completed
    await update_lesson_series(series)

    status = "завершённой" if series.is_completed else "незавершённой"
    await callback.answer(f"✅ Серия отмечена как {status}")

    # Возвращаемся к просмотру серии
    await view_series(callback)


@router.callback_query(F.data.startswith("series_toggle_active_"))
@admin_required
async def toggle_series_active(callback: CallbackQuery):
    """Переключить активность серии"""
    series_id = int(callback.data.split("_")[3])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        return

    series.is_active = not series.is_active
    await update_lesson_series(series)

    status = "активирована" if series.is_active else "деактивирована"
    await callback.answer(f"✅ Серия {status}")

    # Возвращаемся к просмотру серии
    await view_series(callback)


@router.callback_query(F.data.startswith("series_delete_"))
@admin_required
async def confirm_delete_series(callback: CallbackQuery):
    """Подтверждение удаления серии"""
    series_id = int(callback.data.split("_")[2])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        return

    text = (
        f"⚠️ <b>Подтверждение удаления серии</b>\n\n"
        f"Вы действительно хотите удалить серию:\n"
        f"<b>{series.display_name}</b>\n\n"
        f"Уроков в серии: {series.total_lessons}\n\n"
        f"⚠️ <b>Внимание:</b> Уроки НЕ будут удалены, но у них станет series_id = NULL"
    )

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"series_delete_confirm_{series.id}"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"series_view_{series.id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("series_delete_confirm_"))
@admin_required
async def delete_series_confirmed(callback: CallbackQuery):
    """Удалить серию после подтверждения"""
    series_id = int(callback.data.split("_")[3])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        return

    teacher_id = series.teacher_id
    series_name = series.display_name

    await delete_lesson_series(series_id)

    await callback.message.edit_text(
        f"✅ <b>Серия удалена:</b> {series_name}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 К списку серий", callback_data=f"series_teacher_{teacher_id}")
        ]])
    )
    await callback.answer("✅ Серия удалена")


@router.callback_query(F.data.startswith("series_edit_year_"))
@admin_required
async def edit_series_year(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование года серии"""
    series_id = int(callback.data.split("_")[3])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        return

    await state.update_data(series_id=series_id)
    await state.set_state(SeriesStates.edit_year)

    await callback.message.edit_text(
        f"📅 <b>Редактирование года серии</b>\n\n"
        f"Текущий год: <b>{series.year}</b>\n\n"
        f"Введите новый год (2000-2050):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_view_{series_id}")
        ]])
    )
    await callback.answer()


@router.message(SeriesStates.edit_year)
@admin_required
async def save_series_year(message: Message, state: FSMContext):
    """Сохранить новый год серии"""
    data = await state.get_data()
    series_id = data.get("series_id")

    series = await get_series_by_id(series_id)
    if not series:
        await message.answer("❌ Серия не найдена")
        await state.clear()
        return

    try:
        year = int(message.text)
        if year < 2000 or year > 2050:
            await message.answer("❌ Год должен быть в диапазоне 2000-2050")
            return
    except ValueError:
        await message.answer("❌ Введите корректный год (число)")
        return

    series.year = year
    await update_lesson_series(series)

    await state.clear()
    await message.answer(
        f"✅ Год серии обновлен: <b>{series.year}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 К серии", callback_data=f"series_view_{series_id}")
        ]])
    )


@router.callback_query(F.data.startswith("series_edit_desc_"))
@admin_required
async def edit_series_description(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование описания серии"""
    series_id = int(callback.data.split("_")[3])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        return

    await state.update_data(series_id=series_id)
    await state.set_state(SeriesStates.edit_description)

    current_desc = series.description if series.description else "не указано"

    await callback.message.edit_text(
        f"📝 <b>Редактирование описания серии</b>\n\n"
        f"Текущее описание: <i>{current_desc}</i>\n\n"
        f"Введите новое описание (или отправьте '-' для удаления):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_view_{series_id}")
        ]])
    )
    await callback.answer()


@router.message(SeriesStates.edit_description)
@admin_required
async def save_series_description(message: Message, state: FSMContext):
    """Сохранить новое описание серии"""
    data = await state.get_data()
    series_id = data.get("series_id")

    series = await get_series_by_id(series_id)
    if not series:
        await message.answer("❌ Серия не найдена")
        await state.clear()
        return

    if message.text == "-":
        series.description = None
        desc_text = "удалено"
    else:
        series.description = message.text
        desc_text = message.text

    await update_lesson_series(series)

    await state.clear()
    await message.answer(
        f"✅ Описание серии обновлено: <i>{desc_text}</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 К серии", callback_data=f"series_view_{series_id}")
        ]])
    )


@router.callback_query(F.data.startswith("series_edit_book_"))
@admin_required
async def edit_series_book(callback: CallbackQuery, state: FSMContext):
    """Изменить книгу серии"""
    series_id = int(callback.data.split("_")[3])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        return

    books = await get_all_books()

    await state.update_data(series_id=series_id)
    await state.set_state(SeriesStates.select_book)

    text = (
        f"📖 <b>Изменение книги для серии</b>\n\n"
        f"Серия: <b>{series.year} - {series.name}</b>\n"
        f"Текущая книга: <b>{series.book_title or 'не указана'}</b>\n\n"
        f"Выберите новую книгу:"
    )

    builder = InlineKeyboardBuilder()

    # Кнопка "Без книги"
    builder.add(InlineKeyboardButton(text="❌ Без книги", callback_data=f"series_set_book_{series_id}_none"))

    for book in books:
        builder.add(InlineKeyboardButton(
            text=book.name,
            callback_data=f"series_set_book_{series_id}_{book.id}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_view_{series_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("series_set_book_"))
@admin_required
async def set_series_book(callback: CallbackQuery, state: FSMContext):
    """Сохранить выбранную книгу"""
    parts = callback.data.split("_")
    series_id = int(parts[3])
    book_id = None if parts[4] == "none" else int(parts[4])

    series = await get_series_by_id(series_id)
    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        await state.clear()
        return

    series.book_id = book_id
    await update_lesson_series(series)

    # Автоматически обновить все уроки в серии
    updated_count = await bulk_update_series_lessons(series_id, book_id=book_id)

    await state.clear()

    # Перезагрузить серию из БД чтобы получить актуальные данные
    series = await get_series_by_id(series_id)
    book_name = series.book_title if series.book_title else "не указана"

    await callback.answer(f"✅ Книга обновлена: {book_name} (обновлено уроков: {updated_count})")

    # Вернуться к просмотру серии - создаем новый текст и клавиатуру
    text = series.full_info

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"series_edit_name_{series.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Редактировать год", callback_data=f"series_edit_year_{series.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Редактировать описание", callback_data=f"series_edit_desc_{series.id}"))
    builder.add(InlineKeyboardButton(text="📖 Изменить книгу", callback_data=f"series_edit_book_{series.id}"))
    builder.add(InlineKeyboardButton(text="📑 Изменить тему", callback_data=f"series_edit_theme_{series.id}"))

    if series.is_completed:
        builder.add(InlineKeyboardButton(text="🔄 Отметить как незавершённую", callback_data=f"series_toggle_completed_{series.id}"))
    else:
        builder.add(InlineKeyboardButton(text="✅ Отметить как завершённую", callback_data=f"series_toggle_completed_{series.id}"))

    if series.is_active:
        builder.add(InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"series_toggle_active_{series.id}"))
    else:
        builder.add(InlineKeyboardButton(text="✅ Активировать", callback_data=f"series_toggle_active_{series.id}"))

    builder.add(InlineKeyboardButton(text="🗑 Удалить серию", callback_data=f"series_delete_{series.id}"))
    builder.add(InlineKeyboardButton(text="🔙 К списку серий", callback_data=f"series_teacher_{series.teacher_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("series_edit_theme_"))
@admin_required
async def edit_series_theme(callback: CallbackQuery, state: FSMContext):
    """Изменить тему серии (или тему книги, если книга с темой)"""
    series_id = int(callback.data.split("_")[3])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        return

    # Проверяем, есть ли у серии книга с темой
    book_has_theme = False
    book_theme_id = None
    book_name = None
    try:
        if series.book and series.book.theme_id:
            book_has_theme = True
            book_theme_id = series.book.theme_id
            book_name = series.book.name
    except Exception:
        pass

    themes = await get_all_themes()

    await state.update_data(series_id=series_id, book_has_theme=book_has_theme, book_id=series.book_id if series.book else None)
    await state.set_state(SeriesStates.select_theme)

    if book_has_theme:
        # У книги есть тема - показываем предупреждение
        text = (
            f"⚠️ <b>Изменение темы для книги</b>\n\n"
            f"Серия: <b>{series.year} - {series.name}</b>\n"
            f"Книга: <b>{book_name}</b>\n\n"
            f"📌 У этой книги уже установлена тема.\n"
            f"Изменение темы изменит её для <b>ВСЕХ</b> серий и уроков этой книги.\n\n"
            f"Текущая тема: <b>{series.theme_name or 'не указана'}</b>\n\n"
            f"Выберите новую тему:"
        )
    else:
        # Книги нет или у книги нет темы - обычное изменение темы серии
        text = (
            f"📑 <b>Изменение темы для серии</b>\n\n"
            f"Серия: <b>{series.year} - {series.name}</b>\n"
            f"Текущая тема: <b>{series.theme_name or 'не указана'}</b>\n\n"
            f"Выберите новую тему:"
        )

    builder = InlineKeyboardBuilder()

    # Кнопка "Без темы"
    builder.add(InlineKeyboardButton(text="❌ Без темы", callback_data=f"series_set_theme_{series_id}_none"))

    for theme in themes:
        builder.add(InlineKeyboardButton(
            text=theme.name,
            callback_data=f"series_set_theme_{series_id}_{theme.id}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_view_{series_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("series_set_theme_"))
@admin_required
async def set_series_theme(callback: CallbackQuery, state: FSMContext):
    """Сохранить выбранную тему (для серии или для книги)"""
    parts = callback.data.split("_")
    series_id = int(parts[3])
    theme_id = None if parts[4] == "none" else int(parts[4])

    data = await state.get_data()
    book_has_theme = data.get("book_has_theme", False)
    book_id = data.get("book_id")

    series = await get_series_by_id(series_id)
    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        await state.clear()
        return

    updated_count = 0

    if book_has_theme and book_id:
        # У книги есть тема - меняем тему книги + обновляем ВСЕ уроки этой книги
        book = series.book
        book.theme_id = theme_id
        await update_book(book)

        # Обновить все уроки всех серий этой книги
        updated_count = await bulk_update_book_lessons(book_id, theme_id=theme_id)
    else:
        # Книги нет или у неё нет темы - меняем тему серии
        series.theme_id = theme_id
        await update_lesson_series(series)

        # Автоматически обновить все уроки в серии
        updated_count = await bulk_update_series_lessons(series_id, theme_id=theme_id)

    await state.clear()

    # Перезагрузить серию из БД чтобы получить актуальные данные
    series = await get_series_by_id(series_id)
    theme_name = series.theme_name if series.theme_name else "не указана"

    if book_has_theme:
        await callback.answer(f"✅ Тема книги обновлена: {theme_name} (обновлено уроков во всех сериях: {updated_count})")
    else:
        await callback.answer(f"✅ Тема серии обновлена: {theme_name} (обновлено уроков: {updated_count})")

    # Вернуться к просмотру серии - создаем новый текст и клавиатуру
    text = series.full_info

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"series_edit_name_{series.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Редактировать год", callback_data=f"series_edit_year_{series.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Редактировать описание", callback_data=f"series_edit_desc_{series.id}"))
    builder.add(InlineKeyboardButton(text="📖 Изменить книгу", callback_data=f"series_edit_book_{series.id}"))
    builder.add(InlineKeyboardButton(text="📑 Изменить тему", callback_data=f"series_edit_theme_{series.id}"))

    if series.is_completed:
        builder.add(InlineKeyboardButton(text="🔄 Отметить как незавершённую", callback_data=f"series_toggle_completed_{series.id}"))
    else:
        builder.add(InlineKeyboardButton(text="✅ Отметить как завершённую", callback_data=f"series_toggle_completed_{series.id}"))

    if series.is_active:
        builder.add(InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"series_toggle_active_{series.id}"))
    else:
        builder.add(InlineKeyboardButton(text="✅ Активировать", callback_data=f"series_toggle_active_{series.id}"))

    builder.add(InlineKeyboardButton(text="🗑 Удалить серию", callback_data=f"series_delete_{series.id}"))
    builder.add(InlineKeyboardButton(text="🔙 К списку серий", callback_data=f"series_teacher_{series.teacher_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())


# TODO: Добавить создание новой серии (series_create)
# TODO: Добавить массовое обновление уроков (series_bulk_update)
