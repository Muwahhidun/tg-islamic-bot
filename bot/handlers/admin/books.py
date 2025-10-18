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
    """Сохранить название книги"""
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
    """Сохранить описание книги"""
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
