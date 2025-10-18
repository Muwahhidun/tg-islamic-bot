"""
Управление авторами книг
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required
from bot.services.database_service import (
    get_all_book_authors,
    get_book_author_by_id,
    create_book_author,
    update_book_author,
    delete_book_author,
)

router = Router()


class BookAuthorStates(StatesGroup):
    """Состояния для управления авторами книг"""
    name = State()
    biography = State()


@router.callback_query(F.data == "admin_authors")
@admin_required
async def admin_authors(callback: CallbackQuery):
    """Показать список авторов для управления"""
    authors = await get_all_book_authors()

    builder = InlineKeyboardBuilder()
    for author in authors:
        status = "✅" if author.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {author.name}",
            callback_data=f"edit_author_{author.id}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить автора", callback_data="add_author"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)

    await callback.message.edit_text(
        "✍️ <b>Управление авторами книг</b>\n\n"
        "Выберите автора для редактирования или добавьте нового:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_author")
@admin_required
async def add_author_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление нового автора"""
    await callback.message.edit_text(
        "📝 <b>Добавление нового автора</b>\n\n"
        "Введите имя автора:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_authors")]])
    )
    await state.set_state(BookAuthorStates.name)
    await callback.answer()


@router.message(BookAuthorStates.name)
@admin_required
async def save_author_name(message: Message, state: FSMContext):
    """Сохранить имя автора (создание или редактирование)"""
    data = await state.get_data()
    author_id = data.get("author_id")
    editing_name = data.get("editing_name", False)

    if author_id and editing_name:
        # Редактирование существующего автора
        author = await get_book_author_by_id(author_id)
        if author:
            author.name = message.text
            await update_book_author(author)

            await message.answer(
                f"✅ Имя автора изменено на «{message.text}»",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К автору", callback_data=f"edit_author_{author.id}")]])
            )
            await state.clear()
    else:
        # Создание нового автора
        await state.update_data(name=message.text)

        await message.answer(
            "📝 <b>Добавление нового автора</b>\n\n"
            "Введите биографию автора:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_author_biography")],
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_authors")]
            ])
        )
        await state.set_state(BookAuthorStates.biography)


@router.callback_query(F.data == "skip_author_biography")
@admin_required
async def add_author_skip_biography(callback: CallbackQuery, state: FSMContext):
    """Пропустить биографию автора"""
    data = await state.get_data()

    author = await create_book_author(
        name=data["name"],
        biography="",
        is_active=True
    )

    await callback.message.edit_text(
        f"✅ Автор «{author.name}» успешно добавлен!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку авторов", callback_data="admin_authors")]])
    )
    await state.clear()
    await callback.answer()


@router.message(BookAuthorStates.biography)
@admin_required
async def save_author_biography(message: Message, state: FSMContext):
    """Сохранить биографию автора (создание или редактирование)"""
    data = await state.get_data()
    author_id = data.get("author_id")
    editing_biography = data.get("editing_biography", False)

    if author_id and editing_biography:
        # Редактирование существующего автора
        author = await get_book_author_by_id(author_id)
        if author:
            author.biography = message.text
            await update_book_author(author)

            await message.answer(
                f"✅ Биография автора обновлена",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К автору", callback_data=f"edit_author_{author.id}")]])
            )
            await state.clear()
    else:
        # Создание нового автора
        author = await create_book_author(
            name=data["name"],
            biography=message.text,
            is_active=True
        )

        await message.answer(
            f"✅ Автор «{author.name}» успешно добавлен!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку авторов", callback_data="admin_authors")]])
        )
        await state.clear()


@router.callback_query(F.data.regexp(r"^edit_author_\d+$"))
@admin_required
async def edit_author_menu(callback: CallbackQuery):
    """Показать меню редактирования автора"""
    author_id = int(callback.data.split("_")[2])
    author = await get_book_author_by_id(author_id)

    if not author:
        await callback.answer("❌ Автор не найден", show_alert=True)
        return

    status_text = "✅ Активен" if author.is_active else "❌ Неактивен"
    bio_preview = (author.biography[:100] + "...") if author.biography and len(author.biography) > 100 else (author.biography or "Нет биографии")

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Изменить имя", callback_data=f"edit_author_name_{author.id}"))
    builder.add(InlineKeyboardButton(text="📝 Изменить биографию", callback_data=f"edit_author_bio_{author.id}"))
    builder.add(InlineKeyboardButton(text=f"🔄 Статус: {status_text}", callback_data=f"toggle_author_{author.id}"))
    builder.add(InlineKeyboardButton(text="🗑 Удалить автора", callback_data=f"delete_author_{author.id}"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_authors"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"✍️ <b>Редактирование автора</b>\n\n"
        f"👤 <b>Имя:</b> {author.name}\n"
        f"📖 <b>Биография:</b> {bio_preview}\n"
        f"📊 <b>Статус:</b> {status_text}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_author_name_"))
@admin_required
async def edit_author_name_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение имени автора"""
    author_id = int(callback.data.split("_")[3])
    author = await get_book_author_by_id(author_id)

    if not author:
        await callback.answer("❌ Автор не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"📝 <b>Изменение имени автора</b>\n\n"
        f"Текущее имя: {author.name}\n\n"
        "Введите новое имя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_author_{author.id}")]])
    )
    await state.update_data(author_id=author_id, editing_name=True)
    await state.set_state(BookAuthorStates.name)
    await callback.answer()


@router.callback_query(F.data.startswith("edit_author_bio_"))
@admin_required
async def edit_author_bio_start(callback: CallbackQuery, state: FSMContext):
    """Начать изменение биографии автора"""
    author_id = int(callback.data.split("_")[3])
    author = await get_book_author_by_id(author_id)

    if not author:
        await callback.answer("❌ Автор не найден", show_alert=True)
        return

    current_bio = author.biography or "Нет биографии"
    bio_preview = (current_bio[:200] + "...") if len(current_bio) > 200 else current_bio

    await callback.message.edit_text(
        f"📝 <b>Изменение биографии автора</b>\n\n"
        f"Текущая биография:\n{bio_preview}\n\n"
        "Введите новую биографию:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Удалить биографию", callback_data=f"delete_author_bio_{author.id}")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_author_{author.id}")]
        ])
    )
    await state.update_data(author_id=author_id, editing_biography=True)
    await state.set_state(BookAuthorStates.biography)
    await callback.answer()


@router.callback_query(F.data.startswith("delete_author_bio_"))
@admin_required
async def delete_author_bio(callback: CallbackQuery, state: FSMContext):
    """Удалить биографию автора"""
    author_id = int(callback.data.split("_")[3])
    author = await get_book_author_by_id(author_id)

    if not author:
        await callback.answer("❌ Автор не найден", show_alert=True)
        return

    author.biography = ""
    await update_book_author(author)

    await state.clear()
    await callback.answer("✅ Биография удалена")

    # Вернуться к меню редактирования
    await edit_author_menu(callback)


@router.callback_query(F.data.startswith("toggle_author_"))
@admin_required
async def toggle_author(callback: CallbackQuery):
    """Переключить статус автора"""
    author_id = int(callback.data.split("_")[2])
    author = await get_book_author_by_id(author_id)

    if not author:
        await callback.answer("❌ Автор не найден", show_alert=True)
        return

    author.is_active = not author.is_active
    await update_book_author(author)

    status = "активирован" if author.is_active else "деактивирован"
    await callback.answer(f"✅ Автор {status}")

    # Обновить меню
    await edit_author_menu(callback)


@router.callback_query(F.data.startswith("delete_author_"))
@admin_required
async def delete_author_confirm(callback: CallbackQuery):
    """Подтверждение удаления автора"""
    author_id = int(callback.data.split("_")[2])
    author = await get_book_author_by_id(author_id)

    if not author:
        await callback.answer("❌ Автор не найден", show_alert=True)
        return

    # Подсчет книг автора
    books_count = len(author.books) if author.books else 0

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_author_{author.id}"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_author_{author.id}"))
    builder.adjust(1)

    # Формируем текст предупреждения
    warning_text = f"⚠️ <b>Подтверждение удаления</b>\n\n"
    warning_text += f"Вы уверены, что хотите удалить автора «{author.name}»?\n\n"

    if books_count > 0:
        warning_text += f"⚠️ <b>Внимание!</b> У этого автора есть {books_count} книг(и).\n"
        warning_text += "При удалении автора поле 'Автор' у этих книг станет пустым.\n\n"

    warning_text += "Это действие нельзя отменить!"

    await callback.message.edit_text(
        warning_text,
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_author_"))
@admin_required
async def delete_author_confirmed(callback: CallbackQuery):
    """Удалить автора после подтверждения"""
    author_id = int(callback.data.split("_")[3])
    author = await get_book_author_by_id(author_id)

    if not author:
        await callback.answer("❌ Автор не найден", show_alert=True)
        return

    author_name = author.name
    await delete_book_author(author_id)

    await callback.message.edit_text(
        f"✅ Автор «{author_name}» успешно удалён!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку авторов", callback_data="admin_authors")]])
    )
    await callback.answer()
