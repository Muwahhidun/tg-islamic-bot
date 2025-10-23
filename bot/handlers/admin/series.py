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
    get_series_by_teacher,
    get_series_by_id,
    create_lesson_series,
    update_lesson_series,
    delete_lesson_series,
    get_all_books,
    get_book_by_id,
    get_all_themes,
    bulk_update_series_lessons,
    bulk_update_book_lessons,
    update_book,
    regenerate_series_lessons_titles
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
    # Создание новой серии
    create_name = State()
    create_year = State()
    create_description = State()
    create_book = State()
    create_theme = State()


@router.callback_query(F.data == "admin_series")
@admin_required
async def series_menu(callback: CallbackQuery):
    """Главное меню управления сериями"""
    text = (
        "📁 <b>Управление сериями уроков</b>\n\n"
        "Выберите преподавателя для просмотра его серий:"
    )

    # Получаем всех преподавателей
    teachers = await get_all_lesson_teachers()

    builder = InlineKeyboardBuilder()
    for teacher in teachers:
        # Получаем количество серий преподавателя
        teacher_series = await get_series_by_teacher(teacher.id)
        series_count = len(teacher_series)

        builder.add(InlineKeyboardButton(
            text=f"👤 {teacher.name} ({series_count} сер.)",
            callback_data=f"series_teacher_{teacher.id}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_panel"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("series_teacher_"))
@admin_required
async def show_teacher_series(callback: CallbackQuery):
    """Показать все серии преподавателя"""
    teacher_id = int(callback.data.split("_")[2])
    series_list = await get_series_by_teacher(teacher_id)

    # Получаем имя преподавателя
    from bot.services.database_service import get_lesson_teacher_by_id
    teacher = await get_lesson_teacher_by_id(teacher_id)
    teacher_name = teacher.name if teacher else "Преподаватель"

    if not series_list:
        # Нет серий - показываем пустое меню с кнопкой создания
        text = (
            f"📁 <b>Серии преподавателя {teacher_name}</b>\n\n"
            f"У этого преподавателя пока нет серий."
        )
    else:
        text = f"📁 <b>Серии преподавателя {teacher_name}</b>\n\n"

    builder = InlineKeyboardBuilder()

    # Показываем серии, если есть
    for series in series_list:
        lessons_count = series.total_lessons
        status = "✅" if series.is_completed else "🔄"
        active = "✅" if series.is_active else "❌"

        button_text = f"{status} {series.year} - {series.name} ({lessons_count} ур.) {active}"
        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"series_view_{series.id}"
        ))

    # Всегда показываем кнопку создания
    builder.add(InlineKeyboardButton(text="➕ Создать новую серию", callback_data=f"series_create_teacher_{teacher_id}"))
    builder.add(InlineKeyboardButton(text="🔙 К выбору преподавателя", callback_data="admin_series"))
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
    builder.add(InlineKeyboardButton(text="📄 Редактировать описание", callback_data=f"series_edit_desc_{series.id}"))
    builder.add(InlineKeyboardButton(text="📖 Изменить книгу", callback_data=f"series_edit_book_{series.id}"))

    # Всегда показываем кнопку "Изменить тему" - логика внутри обработчика
    builder.add(InlineKeyboardButton(text="📚 Изменить тему", callback_data=f"series_edit_theme_{series.id}"))

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

    # Сохраняем координаты сообщения для Single-Window UX
    await state.update_data(
        series_id=series_id,
        edit_message_id=callback.message.message_id,
        edit_chat_id=callback.message.chat.id
    )
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

    # Удаляем пользовательское сообщение
    try:
        await message.delete()
    except:
        pass

    series = await get_series_by_id(series_id)
    if not series:
        await message.bot.edit_message_text(
            chat_id=data['edit_chat_id'],
            message_id=data['edit_message_id'],
            text="❌ Серия не найдена"
        )
        await state.clear()
        return

    series.name = message.text.strip()
    await update_lesson_series(series)

    # Регенерируем названия всех уроков этой серии
    updated_lessons = await regenerate_series_lessons_titles(series_id)
    if updated_lessons > 0:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Регенерировано названий уроков: {updated_lessons} (серия {series_id})")

    # Перезагружаем серию с актуальными данными
    series = await get_series_by_id(series_id)

    # Строим полное меню серии
    text = series.full_info

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"series_edit_name_{series.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Редактировать год", callback_data=f"series_edit_year_{series.id}"))
    builder.add(InlineKeyboardButton(text="📄 Редактировать описание", callback_data=f"series_edit_desc_{series.id}"))
    builder.add(InlineKeyboardButton(text="📖 Изменить книгу", callback_data=f"series_edit_book_{series.id}"))
    builder.add(InlineKeyboardButton(text="📚 Изменить тему", callback_data=f"series_edit_theme_{series.id}"))

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

    # Обновляем оригинальное сообщение
    await message.bot.edit_message_text(
        chat_id=data['edit_chat_id'],
        message_id=data['edit_message_id'],
        text=text,
        reply_markup=builder.as_markup()
    )
    await state.clear()


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


@router.callback_query(F.data.startswith("series_delete_") & ~F.data.startswith("series_delete_confirm_"))
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

    # Сохраняем координаты сообщения для Single-Window UX
    await state.update_data(
        series_id=series_id,
        edit_message_id=callback.message.message_id,
        edit_chat_id=callback.message.chat.id
    )
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

    # Удаляем пользовательское сообщение
    try:
        await message.delete()
    except:
        pass

    series = await get_series_by_id(series_id)
    if not series:
        await message.bot.edit_message_text(
            chat_id=data['edit_chat_id'],
            message_id=data['edit_message_id'],
            text="❌ Серия не найдена"
        )
        await state.clear()
        return

    # Валидация года
    try:
        year = int(message.text.strip())
        if year < 2000 or year > 2050:
            # Показываем ошибку в том же окне
            await message.bot.edit_message_text(
                chat_id=data['edit_chat_id'],
                message_id=data['edit_message_id'],
                text=f"❌ <b>Ошибка!</b>\n\nГод должен быть в диапазоне 2000-2050.\n\nВведите корректный год:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_view_{series_id}")
                ]])
            )
            return
    except ValueError:
        # Показываем ошибку в том же окне
        await message.bot.edit_message_text(
            chat_id=data['edit_chat_id'],
            message_id=data['edit_message_id'],
            text=f"❌ <b>Ошибка!</b>\n\nВведите корректный год (число).\n\nПопробуйте снова:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_view_{series_id}")
            ]])
        )
        return

    series.year = year
    await update_lesson_series(series)

    # Регенерируем названия всех уроков этой серии
    updated_lessons = await regenerate_series_lessons_titles(series_id)
    if updated_lessons > 0:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Регенерировано названий уроков: {updated_lessons} (серия {series_id})")

    # Перезагружаем серию с актуальными данными
    series = await get_series_by_id(series_id)

    # Строим полное меню серии
    text = series.full_info

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"series_edit_name_{series.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Редактировать год", callback_data=f"series_edit_year_{series.id}"))
    builder.add(InlineKeyboardButton(text="📄 Редактировать описание", callback_data=f"series_edit_desc_{series.id}"))
    builder.add(InlineKeyboardButton(text="📖 Изменить книгу", callback_data=f"series_edit_book_{series.id}"))
    builder.add(InlineKeyboardButton(text="📚 Изменить тему", callback_data=f"series_edit_theme_{series.id}"))

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

    # Обновляем оригинальное сообщение
    await message.bot.edit_message_text(
        chat_id=data['edit_chat_id'],
        message_id=data['edit_message_id'],
        text=text,
        reply_markup=builder.as_markup()
    )
    await state.clear()


@router.callback_query(F.data.startswith("series_edit_desc_"))
@admin_required
async def edit_series_description(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование описания серии"""
    series_id = int(callback.data.split("_")[3])
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("Серия не найдена", show_alert=True)
        return

    # Сохраняем координаты сообщения для Single-Window UX
    await state.update_data(
        series_id=series_id,
        edit_message_id=callback.message.message_id,
        edit_chat_id=callback.message.chat.id
    )
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

    # Удаляем пользовательское сообщение
    try:
        await message.delete()
    except:
        pass

    series = await get_series_by_id(series_id)
    if not series:
        await message.bot.edit_message_text(
            chat_id=data['edit_chat_id'],
            message_id=data['edit_message_id'],
            text="❌ Серия не найдена"
        )
        await state.clear()
        return

    if message.text.strip() == "-":
        series.description = None
    else:
        series.description = message.text.strip()

    await update_lesson_series(series)

    # Перезагружаем серию с актуальными данными
    series = await get_series_by_id(series_id)

    # Строим полное меню серии
    text = series.full_info

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Редактировать название", callback_data=f"series_edit_name_{series.id}"))
    builder.add(InlineKeyboardButton(text="✏️ Редактировать год", callback_data=f"series_edit_year_{series.id}"))
    builder.add(InlineKeyboardButton(text="📄 Редактировать описание", callback_data=f"series_edit_desc_{series.id}"))
    builder.add(InlineKeyboardButton(text="📖 Изменить книгу", callback_data=f"series_edit_book_{series.id}"))
    builder.add(InlineKeyboardButton(text="📚 Изменить тему", callback_data=f"series_edit_theme_{series.id}"))

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

    # Обновляем оригинальное сообщение
    await message.bot.edit_message_text(
        chat_id=data['edit_chat_id'],
        message_id=data['edit_message_id'],
        text=text,
        reply_markup=builder.as_markup()
    )
    await state.clear()


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
    builder.add(InlineKeyboardButton(text="📄 Редактировать описание", callback_data=f"series_edit_desc_{series.id}"))
    builder.add(InlineKeyboardButton(text="📖 Изменить книгу", callback_data=f"series_edit_book_{series.id}"))
    builder.add(InlineKeyboardButton(text="📚 Изменить тему", callback_data=f"series_edit_theme_{series.id}"))

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
            f"📁 <b>Изменение темы для серии</b>\n\n"
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
    builder.add(InlineKeyboardButton(text="📄 Редактировать описание", callback_data=f"series_edit_desc_{series.id}"))
    builder.add(InlineKeyboardButton(text="📖 Изменить книгу", callback_data=f"series_edit_book_{series.id}"))
    builder.add(InlineKeyboardButton(text="📚 Изменить тему", callback_data=f"series_edit_theme_{series.id}"))

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


# ============= СОЗДАНИЕ НОВОЙ СЕРИИ =============

@router.callback_query(F.data.startswith("series_create_teacher_"))
@admin_required
async def create_series_start(callback: CallbackQuery, state: FSMContext):
    """Начать создание новой серии для преподавателя"""
    teacher_id = int(callback.data.split("_")[3])

    # Сохраняем координаты сообщения для Single-Window UX
    await state.update_data(
        teacher_id=teacher_id,
        create_message_id=callback.message.message_id,
        create_chat_id=callback.message.chat.id
    )
    await state.set_state(SeriesStates.create_name)

    await callback.message.edit_text(
        "📁 <b>Создание новой серии</b>\n\n"
        "Шаг 1/5: Введите название серии:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_teacher_{teacher_id}")
        ]])
    )
    await callback.answer()


@router.message(SeriesStates.create_name)
@admin_required
async def create_series_name(message: Message, state: FSMContext):
    """Сохранить название и запросить год"""
    data = await state.get_data()
    teacher_id = data.get("teacher_id")

    # Удаляем пользовательское сообщение
    try:
        await message.delete()
    except:
        pass

    name = message.text.strip()

    if not name:
        await message.bot.edit_message_text(
            chat_id=data['create_chat_id'],
            message_id=data['create_message_id'],
            text="❌ <b>Ошибка!</b>\n\nНазвание не может быть пустым.\n\nВведите название серии:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_teacher_{teacher_id}")
            ]])
        )
        return

    await state.update_data(name=name)
    await state.set_state(SeriesStates.create_year)

    await message.bot.edit_message_text(
        chat_id=data['create_chat_id'],
        message_id=data['create_message_id'],
        text=f"✅ Название: <b>{name}</b>\n\n"
             f"Шаг 2/5: Введите год серии (2000-2050):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_teacher_{teacher_id}")
        ]])
    )


@router.message(SeriesStates.create_year)
@admin_required
async def create_series_year(message: Message, state: FSMContext):
    """Сохранить год и запросить описание"""
    data = await state.get_data()
    teacher_id = data.get("teacher_id")

    # Удаляем пользовательское сообщение
    try:
        await message.delete()
    except:
        pass

    # Валидация года
    try:
        year = int(message.text.strip())
        if year < 2000 or year > 2050:
            await message.bot.edit_message_text(
                chat_id=data['create_chat_id'],
                message_id=data['create_message_id'],
                text="❌ <b>Ошибка!</b>\n\nГод должен быть в диапазоне 2000-2050.\n\nВведите год:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_teacher_{teacher_id}")
                ]])
            )
            return
    except ValueError:
        await message.bot.edit_message_text(
            chat_id=data['create_chat_id'],
            message_id=data['create_message_id'],
            text="❌ <b>Ошибка!</b>\n\nВведите корректный год (число).\n\nПопробуйте снова:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_teacher_{teacher_id}")
            ]])
        )
        return

    await state.update_data(year=year)
    await state.set_state(SeriesStates.create_description)

    await message.bot.edit_message_text(
        chat_id=data['create_chat_id'],
        message_id=data['create_message_id'],
        text=f"✅ Год: <b>{year}</b>\n\n"
             f"Шаг 3/5: Введите описание серии:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="series_create_skip_desc")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_teacher_{teacher_id}")]
        ])
    )


@router.callback_query(F.data == "series_create_skip_desc")
@admin_required
async def create_series_skip_description(callback: CallbackQuery, state: FSMContext):
    """Пропустить описание и перейти к выбору книги"""
    await state.update_data(description=None)
    await ask_series_book(callback, state)


@router.message(SeriesStates.create_description)
@admin_required
async def create_series_description(message: Message, state: FSMContext):
    """Сохранить описание и перейти к выбору книги"""
    data = await state.get_data()

    # Удаляем пользовательское сообщение
    try:
        await message.delete()
    except:
        pass

    description = message.text.strip()
    await state.update_data(description=description)

    # Переходим к выбору книги (используем те же координаты сообщения)
    books = await get_all_books()
    teacher_id = data.get("teacher_id")

    await state.set_state(SeriesStates.create_book)

    text = (
        f"✅ Описание сохранено\n\n"
        f"Шаг 4/5: Выберите книгу для серии:"
    )

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❌ Без книги", callback_data="series_create_book_none"))

    for book in books:
        builder.add(InlineKeyboardButton(
            text=book.name,
            callback_data=f"series_create_book_{book.id}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_teacher_{teacher_id}"))
    builder.adjust(1)

    await message.bot.edit_message_text(
        chat_id=data['create_chat_id'],
        message_id=data['create_message_id'],
        text=text,
        reply_markup=builder.as_markup()
    )


async def ask_series_book(callback: CallbackQuery, state: FSMContext):
    """Общая функция для запроса выбора книги (для пропуска описания)"""
    data = await state.get_data()
    teacher_id = data.get("teacher_id")

    books = await get_all_books()

    await state.set_state(SeriesStates.create_book)

    text = (
        f"Шаг 4/5: Выберите книгу для серии:"
    )

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❌ Без книги", callback_data="series_create_book_none"))

    for book in books:
        builder.add(InlineKeyboardButton(
            text=book.name,
            callback_data=f"series_create_book_{book.id}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_teacher_{teacher_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("series_create_book_"))
@admin_required
async def create_series_book(callback: CallbackQuery, state: FSMContext):
    """Сохранить выбор книги и решить, нужна ли тема"""
    parts = callback.data.split("_")
    book_id = None if parts[3] == "none" else int(parts[3])

    # Проверяем, нужно ли спрашивать тему
    need_theme = True
    book_theme_id = None

    if book_id:
        book = await get_book_by_id(book_id)
        if book and book.theme_id:
            # У книги есть тема - не спрашиваем
            need_theme = False
            book_theme_id = book.theme_id

    # Сохраняем все данные ПЕРЕД переходом дальше
    if need_theme:
        # Книги нет или у неё нет темы - будем спрашивать тему
        await state.update_data(book_id=book_id, book_has_theme=False)
        await ask_series_theme(callback, state)
    else:
        # У книги есть тема - сохраняем её и создаём серию
        await state.update_data(book_id=book_id, theme_id=book_theme_id, book_has_theme=True)
        await create_series_final(callback, state)


async def ask_series_theme(callback: CallbackQuery, state: FSMContext):
    """Запросить выбор темы"""
    data = await state.get_data()
    teacher_id = data.get("teacher_id")

    themes = await get_all_themes()

    await state.set_state(SeriesStates.create_theme)

    text = (
        f"✅ Книга выбрана\n\n"
        f"Шаг 5/5: Выберите тему для серии:"
    )

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="❌ Без темы", callback_data="series_create_theme_none"))

    for theme in themes:
        builder.add(InlineKeyboardButton(
            text=theme.name,
            callback_data=f"series_create_theme_{theme.id}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"series_teacher_{teacher_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("series_create_theme_"))
@admin_required
async def create_series_theme(callback: CallbackQuery, state: FSMContext):
    """Сохранить выбор темы и создать серию"""
    parts = callback.data.split("_")
    theme_id = None if parts[3] == "none" else int(parts[3])

    await state.update_data(theme_id=theme_id)
    await create_series_final(callback, state)


async def create_series_final(callback: CallbackQuery, state: FSMContext):
    """Финальное создание серии"""
    data = await state.get_data()

    teacher_id = data.get("teacher_id")
    name = data.get("name")
    year = data.get("year")
    description = data.get("description")
    book_id = data.get("book_id")
    theme_id = data.get("theme_id")
    book_has_theme = data.get("book_has_theme", False)

    # Создаём серию
    created_series = await create_lesson_series(
        name=name,
        year=year,
        teacher_id=teacher_id,
        description=description,
        book_id=book_id,
        theme_id=theme_id if not book_has_theme else None  # Если у книги есть тема, не сохраняем theme_id в серии
    )

    # Перезагружаем серию из БД, чтобы получить актуальные данные со всеми связями
    created_series = await get_series_by_id(created_series.id)

    # Получаем список всех серий преподавателя для показа
    series_list = await get_series_by_teacher(teacher_id)
    from bot.services.database_service import get_lesson_teacher_by_id
    teacher = await get_lesson_teacher_by_id(teacher_id)
    teacher_name = teacher.name if teacher else "Преподаватель"

    text = f"📁 <b>Серии преподавателя {teacher_name}</b>\n\n"

    builder = InlineKeyboardBuilder()

    # Показываем все серии
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
    builder.add(InlineKeyboardButton(text="🔙 К выбору преподавателя", callback_data="admin_series"))
    builder.adjust(1)

    # Обновляем оригинальное сообщение - возвращаемся к списку серий
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer(f"✅ Серия создана: {created_series.year} - {created_series.name}")

    await state.clear()


# TODO: Добавить массовое обновление уроков (series_bulk_update)
