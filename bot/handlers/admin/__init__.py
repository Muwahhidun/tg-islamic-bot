"""
Административные обработчики - модульная структура
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required

# Импорт роутеров из модулей
from . import themes, authors, teachers, books, lessons, users, stats

# Главный роутер для админ-панели
router = Router()

# Включение всех подроутеров
router.include_router(themes.router)
router.include_router(authors.router)
router.include_router(teachers.router)
router.include_router(books.router)
router.include_router(lessons.router)
router.include_router(users.router)
router.include_router(stats.router)


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
    builder.adjust(1)  # По одной кнопке в ряд

    await message.answer(
        "🛠️ <b>Административная панель</b>\n\n"
        "Выберите раздел для управления:",
        reply_markup=builder.as_markup()
    )
