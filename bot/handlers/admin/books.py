"""
Управление книгами
"""
import logging

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
    regenerate_book_lessons_titles,
)

logger = logging.getLogger(__name__)

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
    books = await get_all_books()

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
    await state.update_data(
        create_message_id=callback.message.message_id,
        create_chat_id=callback.message.chat.id
    )
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
    new_name = message.text.strip()

    # Проверка уникальности названия
    all_books = await get_all_books()
    book_id = data.get("book_id")
    existing_book = next((b for b in all_books if b.name == new_name and (not book_id or b.id != book_id)), None)

    if existing_book:
        # Удаляем сообщение пользователя
        try:
            await message.delete()
        except:
            pass

        # Определяем координаты окна в зависимости от режима
        if book_id:
            # Режим редактирования
            chat_id = data.get("edit_chat_id")
            message_id = data.get("edit_message_id")
            cancel_callback = f"edit_book_{book_id}"
        else:
            # Режим создания
            chat_id = data.get("create_chat_id")
            message_id = data.get("create_message_id")
            cancel_callback = "admin_books"

        # Обновляем исходное окно с ошибкой
        if chat_id and message_id:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"❌ <b>Ошибка!</b>\n\nКнига с названием «{new_name}» уже существует!\n\nВведите другое название:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 Отмена", callback_data=cancel_callback)
                ]])
            )
        return

    # Проверяем, это редактирование или создание
    if "book_id" in data:
        # Редактирование существующей книги
        book_id = data["book_id"]
        book = await get_book_by_id(book_id)
        if book:
            old_name = book.name
            book.name = new_name
            await update_book(book)

            # Регенерируем тайтлы всех уроков этой книги
            if old_name != new_name:
                updated_lessons = await regenerate_book_lessons_titles(book_id)
                if updated_lessons > 0:
                    logger.info(f"Регенерировано названий уроков: {updated_lessons} (книга {book_id})")

            # Удаляем сообщение пользователя
            try:
                await message.delete()
            except:
                pass

            # Получаем сохранённые данные из state
            edit_message_id = data.get("edit_message_id")
            edit_chat_id = data.get("edit_chat_id")

            # Очищаем state
            await state.clear()

            # Перезагружаем книгу из БД для получения свежих данных
            book = await get_book_by_id(book_id)

            # Формируем меню редактирования (как в edit_book_menu)
            theme_name = book.theme.name if book.theme else "Не указана"
            author_name = book.author.name if book.author else "Не указан"
            status = "Активна" if book.is_active else "Неактивна"

            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"edit_book_name_{book.id}"))
            builder.add(InlineKeyboardButton(text="📄 Изменить описание", callback_data=f"edit_book_description_{book.id}"))
            builder.add(InlineKeyboardButton(text="📚 Изменить тему", callback_data=f"edit_book_theme_{book.id}"))
            builder.add(InlineKeyboardButton(text="✍️ Изменить автора", callback_data=f"edit_book_author_{book.id}"))
            toggle_text = "❌ Деактивировать" if book.is_active else "✅ Активировать"
            builder.add(InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_book_{book.id}"))
            builder.add(InlineKeyboardButton(text="🗑️ Удалить книгу", callback_data=f"delete_book_{book.id}"))
            builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_books"))
            builder.adjust(1)

            info = (
                f"📖 <b>Редактирование книги</b>\n\n"
                f"<b>Название:</b> {book.name}\n"
                f"<b>Описание:</b> {book.desc or 'Не указано'}\n"
                f"<b>Тема:</b> {theme_name}\n"
                f"<b>Автор:</b> {author_name}\n"
                f"<b>Статус:</b> {status}\n\n"
                f"Выберите действие:"
            )

            # Обновляем оригинальное сообщение
            if edit_message_id and edit_chat_id:
                try:
                    await message.bot.edit_message_text(
                        chat_id=edit_chat_id,
                        message_id=edit_message_id,
                        text=info,
                        reply_markup=builder.as_markup()
                    )
                except Exception as e:
                    # Если не получилось отредактировать, отправляем новое
                    await message.answer(info, reply_markup=builder.as_markup())
    else:
        # Создание новой книги
        # Удаляем сообщение пользователя
        await message.delete()

        # Получаем сохранённые данные из state
        create_message_id = data.get("create_message_id")
        create_chat_id = data.get("create_chat_id")

        await state.update_data(name=new_name)

        # Обновляем оригинальное сообщение
        if create_message_id and create_chat_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=create_chat_id,
                    message_id=create_message_id,
                    text="📝 <b>Добавление новой книги</b>\n\n"
                         "Введите описание книги:",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_book_description")],
                        [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_books")]
                    ])
                )
            except:
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
    builder.add(InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_book_theme"))
    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_books"))
    builder.adjust(1)

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
        book = await get_book_by_id(book_id)
        if book:
            book.desc = message.text
            await update_book(book)

            # Удаляем сообщение пользователя
            try:
                await message.delete()
            except:
                pass

            # Получаем сохранённые данные из state
            edit_message_id = data.get("edit_message_id")
            edit_chat_id = data.get("edit_chat_id")

            # Очищаем state
            await state.clear()

            # Перезагружаем книгу из БД для получения свежих данных
            book = await get_book_by_id(book_id)

            # Формируем меню редактирования (как в edit_book_menu)
            theme_name = book.theme.name if book.theme else "Не указана"
            author_name = book.author.name if book.author else "Не указан"
            status = "Активна" if book.is_active else "Неактивна"

            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"edit_book_name_{book.id}"))
            builder.add(InlineKeyboardButton(text="📄 Изменить описание", callback_data=f"edit_book_description_{book.id}"))
            builder.add(InlineKeyboardButton(text="📚 Изменить тему", callback_data=f"edit_book_theme_{book.id}"))
            builder.add(InlineKeyboardButton(text="✍️ Изменить автора", callback_data=f"edit_book_author_{book.id}"))
            toggle_text = "❌ Деактивировать" if book.is_active else "✅ Активировать"
            builder.add(InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_book_{book.id}"))
            builder.add(InlineKeyboardButton(text="🗑️ Удалить книгу", callback_data=f"delete_book_{book.id}"))
            builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_books"))
            builder.adjust(1)

            info = (
                f"📖 <b>Редактирование книги</b>\n\n"
                f"<b>Название:</b> {book.name}\n"
                f"<b>Описание:</b> {book.desc or 'Не указано'}\n"
                f"<b>Тема:</b> {theme_name}\n"
                f"<b>Автор:</b> {author_name}\n"
                f"<b>Статус:</b> {status}\n\n"
                f"Выберите действие:"
            )

            # Обновляем оригинальное сообщение
            if edit_message_id and edit_chat_id:
                try:
                    await message.bot.edit_message_text(
                        chat_id=edit_chat_id,
                        message_id=edit_message_id,
                        text=info,
                        reply_markup=builder.as_markup()
                    )
                except Exception as e:
                    # Если не получилось отредактировать, отправляем новое
                    await message.answer(info, reply_markup=builder.as_markup())
    else:
        # Создание новой книги
        # Удаляем сообщение пользователя
        await message.delete()

        # Получаем сохранённые данные из state
        create_message_id = data.get("create_message_id")
        create_chat_id = data.get("create_chat_id")

        await state.update_data(desc=message.text)

        # Получаем список тем
        themes = await get_all_themes()

        builder = InlineKeyboardBuilder()
        for theme in themes:
            builder.add(InlineKeyboardButton(text=theme.name, callback_data=f"select_theme_{theme.id}"))
        builder.add(InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_book_theme"))
        builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_books"))
        builder.adjust(1)  # По одной кнопке в строке

        # Обновляем оригинальное сообщение
        if create_message_id and create_chat_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=create_chat_id,
                    message_id=create_message_id,
                    text="📝 <b>Добавление новой книги</b>\n\n"
                         "Выберите тему для книги:",
                    reply_markup=builder.as_markup()
                )
            except:
                await message.answer(
                    "📝 <b>Добавление новой книги</b>\n\n"
                    "Выберите тему для книги:",
                    reply_markup=builder.as_markup()
                )
        await state.set_state(BookStates.theme_id)


@router.callback_query(F.data == "skip_book_theme")
@admin_required
async def skip_book_theme(callback: CallbackQuery, state: FSMContext):
    """Пропустить выбор темы"""
    await state.update_data(theme_id=None)

    # Получаем список авторов
    authors = await get_all_book_authors()

    builder = InlineKeyboardBuilder()
    for author in authors:
        builder.add(InlineKeyboardButton(text=author.name, callback_data=f"select_author_{author.id}"))
    builder.add(InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_book_author"))
    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_books"))
    builder.adjust(1)

    await callback.message.edit_text(
        "📝 <b>Добавление новой книги</b>\n\n"
        "Выберите автора книги:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BookStates.author_id)
    await callback.answer()


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
    builder.add(InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_book_author"))
    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_books"))
    builder.adjust(1)  # По одной кнопке в строке

    await callback.message.edit_text(
        "📝 <b>Добавление новой книги</b>\n\n"
        "Выберите автора книги:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(BookStates.author_id)
    await callback.answer()


@router.callback_query(F.data == "skip_book_author")
@admin_required
async def skip_book_author(callback: CallbackQuery, state: FSMContext):
    """Пропустить выбор автора"""
    data = await state.get_data()

    # Создаём книгу
    book = await create_book(
        name=data["name"],
        desc=data.get("desc", ""),
        theme_id=data.get("theme_id"),
        author_id=None,
        is_active=True
    )

    # Получаем сохранённые данные из state
    create_message_id = data.get("create_message_id")
    create_chat_id = data.get("create_chat_id")

    # Очищаем state
    await state.clear()

    # Загружаем весь список книг
    books = await get_all_books()

    # Строим список с кнопками (как в admin_books)
    builder = InlineKeyboardBuilder()
    for book_item in books:
        status = "✅" if book_item.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {book_item.name}",
            callback_data=f"edit_book_{book_item.id}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить книгу", callback_data="add_book"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)

    # Обновляем оригинальное сообщение
    if create_message_id and create_chat_id:
        try:
            await callback.bot.edit_message_text(
                chat_id=create_chat_id,
                message_id=create_message_id,
                text="📖 <b>Управление книгами</b>\n\n"
                     "Выберите книгу для редактирования или добавьте новую:",
                reply_markup=builder.as_markup()
            )
        except:
            await callback.message.edit_text(
                "📖 <b>Управление книгами</b>\n\n"
                "Выберите книгу для редактирования или добавьте новую:",
                reply_markup=builder.as_markup()
            )
    await callback.answer()


@router.callback_query(F.data.regexp(r"^select_author_\d+$"))
@admin_required
async def select_author_for_book(callback: CallbackQuery, state: FSMContext):
    """Выбрать автора для книги"""
    author_id = int(callback.data.split("_")[2])
    data = await state.get_data()

    # Создаём книгу
    book = await create_book(
        name=data["name"],
        desc=data.get("desc", ""),
        theme_id=data.get("theme_id"),
        author_id=author_id,
        is_active=True
    )

    # Получаем сохранённые данные из state
    create_message_id = data.get("create_message_id")
    create_chat_id = data.get("create_chat_id")

    # Очищаем state
    await state.clear()

    # Загружаем весь список книг
    books = await get_all_books()

    # Строим список с кнопками (как в admin_books)
    builder = InlineKeyboardBuilder()
    for book_item in books:
        status = "✅" if book_item.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {book_item.name}",
            callback_data=f"edit_book_{book_item.id}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить книгу", callback_data="add_book"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)

    # Обновляем оригинальное сообщение
    if create_message_id and create_chat_id:
        try:
            await callback.bot.edit_message_text(
                chat_id=create_chat_id,
                message_id=create_message_id,
                text="📖 <b>Управление книгами</b>\n\n"
                     "Выберите книгу для редактирования или добавьте новую:",
                reply_markup=builder.as_markup()
            )
        except:
            await callback.message.edit_text(
                "📖 <b>Управление книгами</b>\n\n"
                "Выберите книгу для редактирования или добавьте новую:",
                reply_markup=builder.as_markup()
            )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_book_name_"))
@admin_required
async def edit_book_name_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование названия книги"""
    book_id = int(callback.data.split("_")[3])
    await state.update_data(
        book_id=book_id,
        edit_message_id=callback.message.message_id,
        edit_chat_id=callback.message.chat.id
    )

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
    await state.update_data(
        book_id=book_id,
        edit_message_id=callback.message.message_id,
        edit_chat_id=callback.message.chat.id
    )

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
    builder.add(InlineKeyboardButton(text="🚫 Без темы", callback_data=f"update_book_theme_{book_id}_none"))
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
    """Обновить тему книги и всех её уроков"""
    parts = callback.data.split("_")
    book_id = int(parts[3])
    theme_id = int(parts[4])

    book = await get_book_by_id(book_id)
    if book:
        book.theme_id = theme_id
        await update_book(book)

        # Автоматически обновить все уроки этой книги во всех сериях
        from bot.services.database_service import bulk_update_book_lessons
        updated_count = await bulk_update_book_lessons(book_id, theme_id=theme_id)

        await callback.answer(f"✅ Тема книги обновлена (обновлено уроков: {updated_count})", show_alert=True)
    else:
        await callback.answer("❌ Книга не найдена", show_alert=True)

    # Возвращаемся в меню редактирования книги
    await edit_book_menu(callback)


@router.callback_query(F.data.regexp(r"^update_book_theme_\d+_none$"))
@admin_required
async def update_book_theme_none(callback: CallbackQuery):
    """Убрать тему у книги"""
    parts = callback.data.split("_")
    book_id = int(parts[3])

    book = await get_book_by_id(book_id)
    if book:
        book.theme_id = None
        await update_book(book)

        # Автоматически обновить все уроки этой книги во всех сериях
        from bot.services.database_service import bulk_update_book_lessons
        updated_count = await bulk_update_book_lessons(book_id, theme_id=None)

        await callback.answer(f"✅ Тема убрана (обновлено уроков: {updated_count})", show_alert=True)
    else:
        await callback.answer("❌ Книга не найдена", show_alert=True)

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
    builder.add(InlineKeyboardButton(text="🚫 Без автора", callback_data=f"update_book_author_{book_id}_none"))
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
    if book:
        book.author_id = author_id
        await update_book(book)

    await callback.answer(f"✅ Автор книги обновлен", show_alert=True)

    # Возвращаемся в меню редактирования книги
    await edit_book_menu(callback)


@router.callback_query(F.data.regexp(r"^update_book_author_\d+_none$"))
@admin_required
async def update_book_author_none(callback: CallbackQuery):
    """Убрать автора у книги"""
    parts = callback.data.split("_")
    book_id = int(parts[3])

    book = await get_book_by_id(book_id)
    if book:
        book.author_id = None
        await update_book(book)

    await callback.answer(f"✅ Автор убран", show_alert=True)

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

    book.is_active = not book.is_active
    await update_book(book)

    status_text = "активирована" if book.is_active else "деактивирована"
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
        warning_text += "Уроки останутся в системе, но будут отвязаны от книги.\n\n"

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
@router.callback_query(F.data.regexp(r"^edit_book_\d+$"))
@admin_required
async def edit_book_menu(callback: CallbackQuery):
    """Показать меню редактирования книги"""
    book_id = int(callback.data.split("_")[2])
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
    builder.add(InlineKeyboardButton(text="📄 Изменить описание", callback_data=f"edit_book_description_{book.id}"))
    builder.add(InlineKeyboardButton(text="📚 Изменить тему", callback_data=f"edit_book_theme_{book.id}"))
    builder.add(InlineKeyboardButton(text="✍️ Изменить автора", callback_data=f"edit_book_author_{book.id}"))

    # Кнопка активации/деактивации
    toggle_text = "❌ Деактивировать" if book.is_active else "✅ Активировать"
    builder.add(InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_book_{book.id}"))

    builder.add(InlineKeyboardButton(text="🗑️ Удалить книгу", callback_data=f"delete_book_{book.id}"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_books"))
    builder.adjust(1)

    text = f"📖 <b>Редактирование книги</b>\n\n"
    text += f"<b>Название:</b> {book.name}\n"
    text += f"<b>Описание:</b> {book.desc or 'Не указано'}\n"
    text += f"<b>Тема:</b> {theme_name}\n"
    text += f"<b>Автор:</b> {author_name}\n"
    text += f"<b>Статус:</b> {status}\n\n"
    text += "Выберите действие:"

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
