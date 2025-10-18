"""
Административные обработчики
"""
from typing import Dict, List, Optional, Union
from datetime import datetime

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.config import config
from bot.utils.decorators import admin_required
from bot.services.database_service import (
    get_all_themes,
    get_theme_by_id,
    create_theme,
    update_theme,
    delete_theme,
    get_all_book_authors,
    get_book_author_by_id,
    create_book_author,
    update_book_author,
    delete_book_author,
    get_all_lesson_teachers,
    get_lesson_teacher_by_id,
    create_lesson_teacher,
    update_lesson_teacher,
    delete_lesson_teacher,
    get_all_books,
    get_book_by_id,
    create_book,
    update_book,
    delete_book,
    get_all_lessons,
    get_lesson_by_id,
    create_lesson,
    update_lesson,
    delete_lesson,
    get_user_by_telegram_id,
    UserService,
    RoleService
)
from bot.models import Theme, BookAuthor, LessonTeacher, Book, Lesson

router = Router()


class ThemeStates(StatesGroup):
    """Состояния для управления темами"""
    name = State()
    description = State()


class BookAuthorStates(StatesGroup):
    """Состояния для управления авторами книг"""
    name = State()
    biography = State()


class LessonTeacherStates(StatesGroup):
    """Состояния для управления преподавателями"""
    name = State()
    biography = State()


class BookStates(StatesGroup):
    """Состояния для управления книгами"""
    name = State()
    description = State()
    theme_id = State()
    author_id = State()


class LessonStates(StatesGroup):
    """Состояния для управления уроками"""
    title = State()
    description = State()
    book_id = State()
    teacher_id = State()
    lesson_number = State()
    duration_minutes = State()
    tags = State()
    audio_file = State()


class UserStates(StatesGroup):
    """Состояния для управления пользователями"""
    role = State()


@router.message(Command("admin"))
@admin_required
async def admin_panel(message: Message):
    """Показать административную панель"""
    builder = InlineKeyboardBuilder()
    
    builder.add(InlineKeyboardButton(text="📚 Управление темами", callback_data="admin_themes"))
    builder.add(InlineKeyboardButton(text="✍️ Управление авторами", callback_data="admin_authors"))
    builder.add(InlineKeyboardButton(text="👨‍🏫 Управление преподавателями", callback_data="admin_teachers"))
    builder.add(InlineKeyboardButton(text="📖 Управление книгами", callback_data="admin_books"))
    builder.add(InlineKeyboardButton(text="🎧 Управление уроками", callback_data="admin_lessons"))
    builder.add(InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users"))
    builder.add(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.adjust(2)
    
    await message.answer(
        "🛠️ <b>Административная панель</b>\n\n"
        "Выберите раздел для управления:",
        reply_markup=builder.as_markup()
    )


# Управление темами
@router.callback_query(F.data == "admin_themes")
@admin_required
async def admin_themes(callback: CallbackQuery):
    """Показать список тем для управления"""
    themes = await get_all_themes()
    
    builder = InlineKeyboardBuilder()
    for theme in themes:
        status = "✅" if theme.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {theme.name}",
            callback_data=f"edit_theme_{theme.id}"
        ))
    
    builder.add(InlineKeyboardButton(text="➕ Добавить тему", callback_data="add_theme"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)
    
    await callback.message.edit_text(
        "📚 <b>Управление темами</b>\n\n"
        "Выберите тему для редактирования или добавьте новую:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_theme")
@admin_required
async def add_theme_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление новой темы"""
    await callback.message.edit_text(
        "📝 <b>Добавление новой темы</b>\n\n"
        "Введите название темы:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_themes")]])
    )
    await state.set_state(ThemeStates.name)
    await callback.answer()


@router.message(ThemeStates.name)
@admin_required
async def add_theme_name(message: Message, state: FSMContext):
    """Сохранить название темы"""
    await state.update_data(name=message.text)
    
    await message.answer(
        "📝 <b>Добавление новой темы</b>\n\n"
        "Введите описание темы (или отправьте /skip для пропуска):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_themes")]])
    )
    await state.set_state(ThemeStates.description)


@router.message(ThemeStates.description, F.text == "/skip")
@admin_required
async def add_theme_skip_description(message: Message, state: FSMContext):
    """Пропустить описание темы"""
    data = await state.get_data()
    
    theme = await create_theme(
        name=data["name"],
        description="",
        is_active=True
    )
    
    await message.answer(
        f"✅ Тема «{theme.name}» успешно добавлена!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку тем", callback_data="admin_themes")]])
    )
    await state.clear()


@router.message(ThemeStates.description)
@admin_required
async def add_theme_description(message: Message, state: FSMContext):
    """Сохранить описание темы"""
    data = await state.get_data()
    
    theme = await create_theme(
        name=data["name"],
        description=message.text,
        is_active=True
    )
    
    await message.answer(
        f"✅ Тема «{theme.name}» успешно добавлена!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку тем", callback_data="admin_themes")]])
    )
    await state.clear()


@router.callback_query(F.data.startswith("edit_theme_"))
@admin_required
async def edit_theme_menu(callback: CallbackQuery):
    """Показать меню редактирования темы"""
    theme_id = int(callback.data.split("_")[2])
    theme = await get_theme_by_id(theme_id)
    
    if not theme:
        await callback.answer("❌ Тема не найдена")
        return
    
    status = "✅ Активна" if theme.is_active else "❌ Неактивна"
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"edit_theme_name_{theme.id}"))
    builder.add(InlineKeyboardButton(text="📝 Изменить описание", callback_data=f"edit_theme_desc_{theme.id}"))
    builder.add(InlineKeyboardButton(text=f"🔄 Статус: {status}", callback_data=f"toggle_theme_{theme.id}"))
    builder.add(InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_theme_{theme.id}"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_themes"))
    builder.adjust(2)
    
    await callback.message.edit_text(
        f"📚 <b>Редактирование темы</b>\n\n"
        f"Название: {theme.name}\n"
        f"Описание: {theme.description or 'Нет описания'}\n"
        f"Статус: {status}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_theme_"))
@admin_required
async def toggle_theme(callback: CallbackQuery):
    """Переключить статус темы"""
    theme_id = int(callback.data.split("_")[2])
    theme = await get_theme_by_id(theme_id)
    
    if not theme:
        await callback.answer("❌ Тема не найдена")
        return
    
    theme.is_active = not theme.is_active
    await update_theme(theme)
    
    status = "активирована" if theme.is_active else "деактивирована"
    await callback.answer(f"✅ Тема {status}")
    await edit_theme_menu(callback)


@router.callback_query(F.data.startswith("delete_theme_"))
@admin_required
async def delete_theme_prompt(callback: CallbackQuery):
    """Подтверждение удаления темы"""
    theme_id = int(callback.data.split("_")[2])
    theme = await get_theme_by_id(theme_id)
    
    if not theme:
        await callback.answer("❌ Тема не найдена")
        return
    
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_theme_{theme.id}"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_theme_menu"))
    
    await callback.message.edit_text(
        f"⚠️ <b>Удаление темы</b>\n\n"
        f"Вы уверены, что хотите удалить тему «{theme.name}»?\n"
        f"Это также удалит все книги и уроки в этой теме!",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_theme_"))
@admin_required
async def confirm_delete_theme(callback: CallbackQuery):
    """Подтвердить удаление темы"""
    theme_id = int(callback.data.split("_")[3])
    theme = await get_theme_by_id(theme_id)
    
    if not theme:
        await callback.answer("❌ Тема не найдена")
        return
    
    await delete_theme(theme_id)
    
    await callback.message.edit_text(
        f"✅ Тема «{theme.name}» и все связанные данные удалены",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку тем", callback_data="admin_themes")]])
    )
    await callback.answer()


@router.callback_query(F.data == "admin_panel")
@admin_required
async def back_to_admin_panel(callback: CallbackQuery):
    """Вернуться в административную панель"""
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(text="📚 Управление темами", callback_data="admin_themes"))
    builder.add(InlineKeyboardButton(text="✍️ Управление авторами", callback_data="admin_authors"))
    builder.add(InlineKeyboardButton(text="👨‍🏫 Управление преподавателями", callback_data="admin_teachers"))
    builder.add(InlineKeyboardButton(text="📖 Управление книгами", callback_data="admin_books"))
    builder.add(InlineKeyboardButton(text="🎧 Управление уроками", callback_data="admin_lessons"))
    builder.add(InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users"))
    builder.add(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.adjust(2)

    await callback.message.edit_text(
        "🛠️ <b>Административная панель</b>\n\n"
        "Выберите раздел для управления:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


# Управление авторами книг
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
        "Введите биографию автора (или отправьте /skip для пропуска):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_authors")]])
    )
    await state.set_state(BookAuthorStates.biography)


@router.message(BookAuthorStates.biography, F.text == "/skip")
@admin_required
async def add_author_skip_biography(message: Message, state: FSMContext):
    """Пропустить биографию автора"""
    data = await state.get_data()
    
    author = await create_book_author(
        name=data["name"],
        biography="",
        is_active=True
    )
    
    await message.answer(
        f"✅ Автор «{author.name}» успешно добавлен!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку авторов", callback_data="admin_authors")]])
    )
    await state.clear()


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


# Управление преподавателями
@router.callback_query(F.data == "admin_teachers")
@admin_required
async def admin_teachers(callback: CallbackQuery):
    """Показать список преподавателей для управления"""
    teachers = await get_all_lesson_teachers()
    
    builder = InlineKeyboardBuilder()
    for teacher in teachers:
        status = "✅" if teacher.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {teacher.name}",
            callback_data=f"edit_teacher_{teacher.id}"
        ))
    
    builder.add(InlineKeyboardButton(text="➕ Добавить преподавателя", callback_data="add_teacher"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)
    
    await callback.message.edit_text(
        "👨‍🏫 <b>Управление преподавателями</b>\n\n"
        "Выберите преподавателя для редактирования или добавьте нового:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_teacher")
@admin_required
async def add_teacher_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление нового преподавателя"""
    await callback.message.edit_text(
        "📝 <b>Добавление нового преподавателя</b>\n\n"
        "Введите имя преподавателя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_teachers")]])
    )
    await state.set_state(LessonTeacherStates.name)
    await callback.answer()


@router.message(LessonTeacherStates.name)
@admin_required
async def add_teacher_name(message: Message, state: FSMContext):
    """Сохранить имя преподавателя"""
    await state.update_data(name=message.text)
    
    await message.answer(
        "📝 <b>Добавление нового преподавателя</b>\n\n"
        "Введите биографию преподавателя (или отправьте /skip для пропуска):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_teachers")]])
    )
    await state.set_state(LessonTeacherStates.biography)


@router.message(LessonTeacherStates.biography, F.text == "/skip")
@admin_required
async def add_teacher_skip_biography(message: Message, state: FSMContext):
    """Пропустить биографию преподавателя"""
    data = await state.get_data()
    
    teacher = await create_lesson_teacher(
        name=data["name"],
        biography="",
        is_active=True
    )
    
    await message.answer(
        f"✅ Преподаватель «{teacher.name}» успешно добавлен!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку преподавателей", callback_data="admin_teachers")]])
    )
    await state.clear()


@router.message(LessonTeacherStates.biography)
@admin_required
async def add_teacher_biography(message: Message, state: FSMContext):
    """Сохранить биографию преподавателя"""
    data = await state.get_data()
    
    teacher = await create_lesson_teacher(
        name=data["name"],
        biography=message.text,
        is_active=True
    )
    
    await message.answer(
        f"✅ Преподаватель «{teacher.name}» успешно добавлен!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку преподавателей", callback_data="admin_teachers")]])
    )
    await state.clear()


# Управление книгами
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
        "Введите описание книги (или отправьте /skip для пропуска):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_books")]])
    )
    await state.set_state(BookStates.description)


@router.message(BookStates.description, F.text == "/skip")
@admin_required
async def add_book_skip_description(message: Message, state: FSMContext):
    """Пропустить описание книги"""
    data = await state.get_data()
    
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


@router.callback_query(F.data.startswith("select_theme_"))
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


@router.callback_query(F.data.startswith("select_author_"))
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


# Управление уроками
@router.callback_query(F.data == "admin_lessons")
@admin_required
async def admin_lessons(callback: CallbackQuery):
    """Показать список уроков для управления"""
    lessons = await get_all_lessons()
    
    builder = InlineKeyboardBuilder()
    for lesson in lessons:
        status = "✅" if lesson.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} Урок {lesson.lesson_number}: {lesson.title}",
            callback_data=f"edit_lesson_{lesson.id}"
        ))
    
    builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)
    
    await callback.message.edit_text(
        "🎧 <b>Управление уроками</b>\n\n"
        "Выберите урок для редактирования или добавьте новый:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_lesson")
@admin_required
async def add_lesson_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление нового урока"""
    # Получаем список книг и преподавателей
    books = await get_all_books()
    teachers = await get_all_lesson_teachers()
    
    if not books or not teachers:
        await callback.message.edit_text(
            "❌ Для добавления урока нужно сначала создать хотя бы одну книгу и одного преподавателя",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_lessons")]])
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Введите название урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.title)
    await callback.answer()


@router.message(LessonStates.title)
@admin_required
async def add_lesson_title(message: Message, state: FSMContext):
    """Сохранить название урока"""
    await state.update_data(title=message.text)
    
    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Введите описание урока (или отправьте /skip для пропуска):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.description)


@router.message(LessonStates.description, F.text == "/skip")
@admin_required
async def add_lesson_skip_description(message: Message, state: FSMContext):
    """Пропустить описание урока"""
    data = await state.get_data()
    
    # Получаем список книг
    books = await get_all_books()
    
    builder = InlineKeyboardBuilder()
    for book in books:
        builder.add(InlineKeyboardButton(text=book.name, callback_data=f"select_book_{book.id}"))
    
    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Выберите книгу для урока:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(LessonStates.book_id)


@router.message(LessonStates.description)
@admin_required
async def add_lesson_description(message: Message, state: FSMContext):
    """Сохранить описание урока"""
    await state.update_data(description=message.text)
    
    # Получаем список книг
    books = await get_all_books()
    
    builder = InlineKeyboardBuilder()
    for book in books:
        builder.add(InlineKeyboardButton(text=book.name, callback_data=f"select_book_{book.id}"))
    
    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Выберите книгу для урока:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(LessonStates.book_id)


@router.callback_query(F.data.startswith("select_book_"))
@admin_required
async def select_book_for_lesson(callback: CallbackQuery, state: FSMContext):
    """Выбрать книгу для урока"""
    book_id = int(callback.data.split("_")[2])
    await state.update_data(book_id=book_id)
    
    # Получаем список преподавателей
    teachers = await get_all_lesson_teachers()
    
    builder = InlineKeyboardBuilder()
    for teacher in teachers:
        builder.add(InlineKeyboardButton(text=teacher.name, callback_data=f"select_teacher_{teacher.id}"))
    
    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Выберите преподавателя урока:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(LessonStates.teacher_id)
    await callback.answer()


@router.callback_query(F.data.startswith("select_teacher_"))
@admin_required
async def select_teacher_for_lesson(callback: CallbackQuery, state: FSMContext):
    """Выбрать преподавателя для урока"""
    teacher_id = int(callback.data.split("_")[2])
    await state.update_data(teacher_id=teacher_id)
    
    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Введите номер урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.lesson_number)
    await callback.answer()


@router.message(LessonStates.lesson_number)
@admin_required
async def add_lesson_number(message: Message, state: FSMContext):
    """Сохранить номер урока"""
    try:
        lesson_number = int(message.text)
        await state.update_data(lesson_number=lesson_number)
        
        await message.answer(
            "📝 <b>Добавление нового урока</b>\n\n"
            "Введите длительность урока в минутах:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )
        await state.set_state(LessonStates.duration_minutes)
    except ValueError:
        await message.answer(
            "❌ Номер урока должен быть числом. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )


@router.message(LessonStates.duration_minutes)
@admin_required
async def add_lesson_duration(message: Message, state: FSMContext):
    """Сохранить длительность урока"""
    try:
        duration_minutes = int(message.text)
        await state.update_data(duration_minutes=duration_minutes)
        
        await message.answer(
            "📝 <b>Добавление нового урока</b>\n\n"
            "Введите теги для урока через запятую (или отправьте /skip для пропуска):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )
        await state.set_state(LessonStates.tags)
    except ValueError:
        await message.answer(
            "❌ Длительность должна быть числом. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )


@router.message(LessonStates.tags, F.text == "/skip")
@admin_required
async def add_lesson_skip_tags(message: Message, state: FSMContext):
    """Пропустить теги урока"""
    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Отправьте аудиофайл урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.audio_file)


@router.message(LessonStates.tags)
@admin_required
async def add_lesson_tags(message: Message, state: FSMContext):
    """Сохранить теги урока"""
    await state.update_data(tags=message.text)
    
    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Отправьте аудиофайл урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.audio_file)


@router.message(LessonStates.audio_file, F.audio)
@admin_required
async def add_lesson_audio(message: Message, state: FSMContext):
    """Сохранить аудиофайл урока"""
    data = await state.get_data()
    
    # Скачиваем аудиофайл
    audio_file = message.audio
    file_info = await message.bot.get_file(audio_file.file_id)
    downloaded_file = await message.bot.download_file(file_info.file_path)
    
    # Сохраняем файл
    import os
    audio_dir = "bot/audio_files"
    os.makedirs(audio_dir, exist_ok=True)
    
    file_path = os.path.join(audio_dir, f"{audio_file.file_unique_id}.mp3")
    with open(file_path, "wb") as f:
        f.write(downloaded_file.getvalue())
    
    lesson = await create_lesson(
        title=data["title"],
        description=data.get("description", ""),
        audio_file_path=file_path,
        duration_minutes=data["duration_minutes"],
        lesson_number=data["lesson_number"],
        book_id=data["book_id"],
        teacher_id=data["teacher_id"],
        tags=data.get("tags", ""),
        is_active=True
    )
    
    await message.answer(
        f"✅ Урок «{lesson.title}» успешно добавлен!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку уроков", callback_data="admin_lessons")]])
    )
    await state.clear()


# Статистика
@router.callback_query(F.data == "admin_stats")
@admin_required
async def admin_stats(callback: CallbackQuery):
    """Показать статистику"""
    themes = await get_all_themes()
    authors = await get_all_book_authors()
    teachers = await get_all_lesson_teachers()
    books = await get_all_books()
    lessons = await get_all_lessons()
    
    active_themes = len([t for t in themes if t.is_active])
    active_authors = len([a for a in authors if a.is_active])
    active_teachers = len([t for t in teachers if t.is_active])
    active_books = len([b for b in books if b.is_active])
    active_lessons = len([l for l in lessons if l.is_active])
    
    total_duration = sum(l.duration_minutes for l in lessons if l.is_active)
    
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"📚 Темы: {active_themes}/{len(themes)}\n"
        f"✍️ Авторы: {active_authors}/{len(authors)}\n"
        f"👨‍🏫 Преподаватели: {active_teachers}/{len(teachers)}\n"
        f"📖 Книги: {active_books}/{len(books)}\n"
        f"🎧 Уроки: {active_lessons}/{len(lessons)}\n"
        f"⏱️ Общая длительность: {total_duration} минут\n\n"
        f"🔥 Активные элементы / Всего элементов"
    )
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel")]])
    )
    await callback.answer()


# Управление пользователями
@router.callback_query(F.data == "admin_users")
@admin_required
async def admin_users(callback: CallbackQuery):
    """Показать список пользователей для управления"""
    # Получаем всех пользователей
    users = await UserService.get_all_users(limit=50)
    
    builder = InlineKeyboardBuilder()
    
    if not users:
        builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
        await callback.message.edit_text(
            "👥 <b>Управление пользователями</b>\n\n"
            "Пользователи не найдены",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return
    
    # Группируем пользователей по ролям
    admins = []
    moderators = []
    regular_users = []
    
    for user in users:
        if user.role and user.role.name == "admin":
            admins.append(user)
        elif user.role and user.role.name == "moderator":
            moderators.append(user)
        else:
            regular_users.append(user)
    
    text = "👥 <b>Управление пользователями</b>\n\n"
    
    if admins:
        text += f"🔹 <b>Администраторы ({len(admins)})</b>\n"
        for user in admins[:5]:  # Показываем только первых 5
            status = "✅" if user.is_active else "❌"
            text += f"{status} {user.first_name or 'Без имени'} (@{user.username or 'no_username'}) - ID: {user.telegram_id}\n"
        if len(admins) > 5:
            text += f"... и еще {len(admins) - 5}\n"
        text += "\n"
    
    if moderators:
        text += f"🔹 <b>Модераторы ({len(moderators)})</b>\n"
        for user in moderators[:5]:  # Показываем только первых 5
            status = "✅" if user.is_active else "❌"
            text += f"{status} {user.first_name or 'Без имени'} (@{user.username or 'no_username'}) - ID: {user.telegram_id}\n"
        if len(moderators) > 5:
            text += f"... и еще {len(moderators) - 5}\n"
        text += "\n"
    
    if regular_users:
        text += f"🔹 <b>Пользователи ({len(regular_users)})</b>\n"
        for user in regular_users[:5]:  # Показываем только первых 5
            status = "✅" if user.is_active else "❌"
            text += f"{status} {user.first_name or 'Без имени'} (@{user.username or 'no_username'}) - ID: {user.telegram_id}\n"
        if len(regular_users) > 5:
            text += f"... и еще {len(regular_users) - 5}\n"
    
    builder.add(InlineKeyboardButton(text="➕ Добавить/изменить роль пользователя", callback_data="add_user_role"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_user_role")
@admin_required
async def add_user_role_start(callback: CallbackQuery, state: FSMContext):
    """Начать процесс добавления/изменения роли пользователя"""
    await callback.message.edit_text(
        "👥 <b>Управление ролями пользователей</b>\n\n"
        "Введите Telegram ID пользователя, которому хотите назначить или изменить роль:\n\n"
        "<i>Чтобы узнать ID пользователя, попросите его отправить команду /id или воспользуйтесь ботами вроде @userinfobot</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_users")]])
    )
    await state.set_state(UserStates.role)
    await callback.answer()


@router.message(UserStates.role)
@admin_required
async def process_user_id(message: Message, state: FSMContext):
    """Обработать ID пользователя"""
    try:
        telegram_id = int(message.text)
        user = await UserService.get_user_by_telegram_id(telegram_id)
        
        if not user:
            # Если пользователя нет в базе, создаем его
            user = await UserService.create_user(
                telegram_id=telegram_id,
                username=None,  # Будет обновлено при первом взаимодействии с ботом
                first_name=None,
                last_name=None,
                role_id=3  # Роль пользователя по умолчанию
            )
        
        # Получаем все роли
        roles = await RoleService.get_all_roles()
        
        builder = InlineKeyboardBuilder()
        for role in roles:
            builder.add(InlineKeyboardButton(
                text=f"{role.name} ({role.description})",
                callback_data=f"set_role_{user.id}_{role.id}"
            ))
        
        builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users"))
        builder.adjust(1)
        
        current_role = user.role.name if user.role else "не назначена"
        
        await message.answer(
            f"👤 <b>Пользователь найден</b>\n\n"
            f"ID: {user.telegram_id}\n"
            f"Имя: {user.first_name or 'Не указано'}\n"
            f"Username: @{user.username or 'не указан'}\n"
            f"Текущая роль: {current_role}\n\n"
            f"Выберите новую роль:",
            reply_markup=builder.as_markup()
        )
        await state.clear()
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат ID. Введите числовой ID пользователя:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_users")]])
        )


@router.callback_query(F.data.startswith("set_role_"))
@admin_required
async def set_user_role(callback: CallbackQuery):
    """Установить роль пользователю"""
    parts = callback.data.split("_")
    user_id = int(parts[2])  # Это внутренний DB ID
    role_id = int(parts[3])

    # Получаем пользователя по внутреннему DB ID и роль
    user = await UserService.get_user_by_id(user_id)
    role = await RoleService.get_role_by_id(role_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    if not role:
        await callback.answer("❌ Роль не найдена", show_alert=True)
        return

    # Обновляем роль пользователя по внутреннему DB ID
    await UserService.update_user_role_by_id(user_id, role_id)

    await callback.answer(f"✅ Роль '{role.name}' назначена пользователю", show_alert=True)
    await admin_users(callback)