"""
Управление книгами
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required
from bot.services.database_service import (
    get_all_books,
    get_book_by_id,
    create_book,
    update_book,
    delete_book,
    get_all_themes,
    get_all_book_authors,
)

router = Router()


class BookStates(StatesGroup):
    """Состояния для управления книгами"""
    name = State()
    description = State()
    theme_id = State()
    author_id = State()


@router.callback_query(F.data == "admin_books")
@admin_required
async def admin_books(callback: CallbackQuery):
    """Показать список книг для управления"""
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"admin_books handler called!!! Fetching books...")

    books = await get_all_books()
    logger.error(f"Found {len(books)} books")

    builder = InlineKeyboardBuilder()
    for book in books:
        status = "✅" if book.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {book.name}",
            callback_data=f"edit_book_{book.id}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить книгу", callback_data="add_book"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)

    await callback.message.edit_text(
        "📖 <b>Управление книгами</b>\n\n"
        "Выберите книгу для редактирования или добавьте новую:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_book")
@admin_required
async def add_book_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление новой книги"""
    # Получаем список тем и авторов
    themes = await get_all_themes()
    authors = await get_all_book_authors()

    if not themes or not authors:
        await callback.message.edit_text(
            "❌ Для добавления книги нужно сначала создать хотя бы одну тему и одного автора",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_books")]])
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📝 <b>Добавление новой книги</b>\n\n"
        "Введите название книги:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_books")]])
    )
    await state.set_state(BookStates.name)
    await callback.answer()


@router.message(BookStates.name)
@admin_required
async def add_book_name(message: Message, state: FSMContext):
    """Сохранить название книги (создание или редактирование)"""
    data = await state.get_data()

    # Проверяем, это редактирование или создание
    if "book_id" in data:
        # Редактирование существующей книги
        book_id = data["book_id"]
        await update_book(book_id, name=message.text)
        await state.clear()

        await message.answer(
            f"✅ Название книги обновлено!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К редактированию", callback_data=f"edit_book_{book_id}")
            ]])
        )
    else:
        # Создание новой книги
        await state.update_data(name=message.text)

        await message.answer(
            "📝 <b>Добавление новой книги</b>\n\n"
            "Введите описание книги:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_book_description")],
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_books")]
            ])
        )
        await state.set_state(BookStates.description)


@router.callback_query(F.data == "skip_book_description")
@admin_required
async def add_book_skip_description(callback: CallbackQuery, state: FSMContext):
    """Пропустить описание книги"""
    data = await state.get_data()

    # Получаем список тем
    themes = await get_all_themes()

    builder = InlineKeyboardBuilder()
    for theme in themes:
        builder.add(InlineKeyboardButton(text=theme.name, callback_data=f"select_theme_{theme.id}"))

    await callback.message.edit_text(
        "📝 <b>Добавление новой книги</b>\n\n"
        "Выберите тему для книги:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BookStates.theme_id)
    await callback.answer()


@router.message(BookStates.description)
@admin_required
async def add_book_description(message: Message, state: FSMContext):
    """Сохранить описание книги (создание или редактирование)"""
    data = await state.get_data()

    # Проверяем, это редактирование или создание
    if "book_id" in data:
        # Редактирование существующей книги
        book_id = data["book_id"]
        await update_book(book_id, description=message.text)
        await state.clear()

        await message.answer(
            f"✅ Описание книги обновлено!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К редактированию", callback_data=f"edit_book_{book_id}")
            ]])
        )
    else:
        # Создание новой книги
        await state.update_data(description=message.text)

        # Получаем список тем
        themes = await get_all_themes()

        builder = InlineKeyboardBuilder()
        for theme in themes:
            builder.add(InlineKeyboardButton(text=theme.name, callback_data=f"select_theme_{theme.id}"))

        await message.answer(
            "📝 <b>Добавление новой книги</b>\n\n"
            "Выберите тему для книги:",
            reply_markup=builder.as_markup()
        )
        await state.set_state(BookStates.theme_id)


@router.callback_query(F.data.regexp(r"^select_theme_\d+$"))
@admin_required
async def select_theme_for_book(callback: CallbackQuery, state: FSMContext):
    """Выбрать тему для книги"""
    theme_id = int(callback.data.split("_")[2])
    await state.update_data(theme_id=theme_id)

    # Получаем список авторов
    authors = await get_all_book_authors()

    builder = InlineKeyboardBuilder()
    for author in authors:
        builder.add(InlineKeyboardButton(text=author.name, callback_data=f"select_author_{author.id}"))

    await callback.message.edit_text(
        "📝 <b>Добавление новой книги</b>\n\n"
        "Выберите автора книги:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BookStates.author_id)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^select_author_\d+$"))
@admin_required
async def select_author_for_book(callback: CallbackQuery, state: FSMContext):
    """Выбрать автора для книги"""
    author_id = int(callback.data.split("_")[2])
    data = await state.get_data()

    book = await create_book(
        name=data["name"],
        description=data.get("description", ""),
        theme_id=data["theme_id"],
        author_id=author_id,
        is_active=True
    )

    await callback.message.edit_text(
        f"✅ Книга «{book.name}» успешно добавлена!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку книг", callback_data="admin_books")]])
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("edit_book_name_"))
@admin_required
async def edit_book_name_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование названия книги"""
    book_id = int(callback.data.split("_")[3])
    await state.update_data(book_id=book_id)

    await callback.message.edit_text(
        "📝 Введите новое название книги:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_book_{book_id}")
        ]])
    )
    await state.set_state(BookStates.name)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_book_description_"))
@admin_required
async def edit_book_description_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование описания книги"""
    book_id = int(callback.data.split("_")[3])
    await state.update_data(book_id=book_id)

    await callback.message.edit_text(
        "📝 Введите новое описание книги:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_book_{book_id}")
        ]])
    )
    await state.set_state(BookStates.description)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_book_theme_"))
@admin_required
async def edit_book_theme_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение темы книги"""
    book_id = int(callback.data.split("_")[3])
    await state.update_data(book_id=book_id)

    themes = await get_all_themes()

    builder = InlineKeyboardBuilder()
    for theme in themes:
        builder.add(InlineKeyboardButton(text=theme.name, callback_data=f"update_book_theme_{book_id}_{theme.id}"))
    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_book_{book_id}"))
    builder.adjust(1)

    await callback.message.edit_text(
        "🏷️ Выберите новую тему для книги:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^update_book_theme_\d+_\d+$"))
@admin_required
async def update_book_theme(callback: CallbackQuery):
    """Обновить тему книги"""
    parts = callback.data.split("_")
    book_id = int(parts[3])
    theme_id = int(parts[4])

    book = await get_book_by_id(book_id)
    await update_book(book_id, theme_id=theme_id)

    await callback.answer(f"✅ Тема книги обновлена", show_alert=True)

    # Возвращаемся в меню редактирования книги
    await edit_book_menu(callback)


@router.callback_query(F.data.startswith("edit_book_author_"))
@admin_required
async def edit_book_author_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение автора книги"""
    book_id = int(callback.data.split("_")[3])
    await state.update_data(book_id=book_id)

    authors = await get_all_book_authors()

    builder = InlineKeyboardBuilder()
    for author in authors:
        builder.add(InlineKeyboardButton(text=author.name, callback_data=f"update_book_author_{book_id}_{author.id}"))
    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_book_{book_id}"))
    builder.adjust(1)

    await callback.message.edit_text(
        "✍️ Выберите нового автора для книги:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^update_book_author_\d+_\d+$"))
@admin_required
async def update_book_author(callback: CallbackQuery):
    """Обновить автора книги"""
    parts = callback.data.split("_")
    book_id = int(parts[3])
    author_id = int(parts[4])

    book = await get_book_by_id(book_id)
    await update_book(book_id, author_id=author_id)

    await callback.answer(f"✅ Автор книги обновлен", show_alert=True)

    # Возвращаемся в меню редактирования книги
    await edit_book_menu(callback)


@router.callback_query(F.data.startswith("toggle_book_"))
@admin_required
async def toggle_book_status(callback: CallbackQuery):
    """Переключить статус активности книги"""
    book_id = int(callback.data.split("_")[2])
    book = await get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Книга не найдена", show_alert=True)
        return

    new_status = not book.is_active
    await update_book(book_id, is_active=new_status)

    status_text = "активирована" if new_status else "деактивирована"
    await callback.answer(f"✅ Книга {status_text}", show_alert=True)

    # Обновляем меню редактирования
    await edit_book_menu(callback)


@router.callback_query(F.data.startswith("delete_book_"))
@admin_required
async def delete_book_confirm(callback: CallbackQuery):
    """Подтверждение удаления книги"""
    book_id = int(callback.data.split("_")[2])
    book = await get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Книга не найдена", show_alert=True)
        return

    # Подсчет количества уроков
    lessons_count = len(book.lessons) if book.lessons else 0

    warning_text = f"⚠️ <b>Удаление книги</b>\n\n"
    warning_text += f"Вы уверены, что хотите удалить книгу «{book.name}»?\n\n"

    if lessons_count > 0:
        warning_text += f"<b>Внимание!</b> У этой книги есть {lessons_count} урок(ов).\n"
        warning_text += "Все уроки будут удалены вместе с книгой!\n\n"

    warning_text += "Это действие нельзя отменить!"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_book_{book_id}"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_book_{book_id}"))
    builder.adjust(1)

    await callback.message.edit_text(warning_text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_book_"))
@admin_required
async def delete_book_confirmed(callback: CallbackQuery):
    """Удалить книгу после подтверждения"""
    book_id = int(callback.data.split("_")[3])
    book = await get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Книга не найдена", show_alert=True)
        return

    book_name = book.name
    await delete_book(book_id)

    await callback.message.edit_text(
        f"✅ Книга «{book_name}» успешно удалена!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 К списку книг", callback_data="admin_books")
        ]])
    )
    await callback.answer()


# ВАЖНО: Этот обработчик должен быть ПОСЛЕДНИМ среди всех edit_book_* обработчиков
# Переделываем на startswith и проверяем внутри функции
@router.callback_query(F.data.startswith("edit_book_"))
async def edit_book_menu(callback: CallbackQuery):
    """Показать меню редактирования книги"""
    import logging
    logger = logging.getLogger(__name__)

    # Проверяем, что это именно edit_book_<id>, а не edit_book_name_ и т.д.
    parts = callback.data.split("_")
    if len(parts) != 3:
        logger.info(f"Skipping {callback.data} - not edit_book_id format")
        return

    if not parts[2].isdigit():
        logger.info(f"Skipping {callback.data} - third part is not digit")
        return

    logger.error(f"✅ edit_book_menu TRIGGERED for {callback.data}!")

    book_id = int(parts[2])
    book = await get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Книга не найдена", show_alert=True)
        return

    # Получаем информацию о теме и авторе
    theme_name = book.theme.name if book.theme else "Не указана"
    author_name = book.author.name if book.author else "Не указан"
    status = "Активна" if book.is_active else "Неактивна"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"edit_book_name_{book.id}"))
    builder.add(InlineKeyboardButton(text="📝 Изменить описание", callback_data=f"edit_book_description_{book.id}"))
    builder.add(InlineKeyboardButton(text="🏷️ Изменить тему", callback_data=f"edit_book_theme_{book.id}"))
    builder.add(InlineKeyboardButton(text="✍️ Изменить автора", callback_data=f"edit_book_author_{book.id}"))

    # Кнопка активации/деактивации
    toggle_text = "❌ Деактивировать" if book.is_active else "✅ Активировать"
    builder.add(InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_book_{book.id}"))

    builder.add(InlineKeyboardButton(text="🗑️ Удалить книгу", callback_data=f"delete_book_{book.id}"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_books"))
    builder.adjust(1)

    text = f"📖 <b>Редактирование книги</b>\n\n"
    text += f"<b>Название:</b> {book.name}\n"
    text += f"<b>Описание:</b> {book.description or 'Не указано'}\n"
    text += f"<b>Тема:</b> {theme_name}\n"
    text += f"<b>Автор:</b> {author_name}\n"
    text += f"<b>Статус:</b> {status}\n\n"
    text += "Выберите действие:"

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ВРЕМЕННЫЙ ОТЛАДОЧНЫЙ ОБРАБОТЧИК - ловит все необработанные callback
# БЕЗ @admin_required чтобы точно сработал
@router.callback_query(F.data.startswith("edit_"))
async def debug_unhandled_callback(callback: CallbackQuery):
    """Временный обработчик для отладки необработанных callback"""
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"DEBUG CATCH-ALL: callback_data = {callback.data}")
    await callback.answer(f"DEBUG: {callback.data}", show_alert=True)
