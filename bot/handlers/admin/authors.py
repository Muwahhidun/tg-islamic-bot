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
async def add_author_name(message: Message, state: FSMContext):
    """Сохранить имя автора"""
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
async def add_author_biography(message: Message, state: FSMContext):
    """Сохранить биографию автора"""
    data = await state.get_data()

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
