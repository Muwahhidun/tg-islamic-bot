"""
Административные обработчики - модульная структура
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required

# Импорт роутеров из модулей
from . import themes, authors, teachers, teachers_series, books, lessons, users, stats

# Главный роутер для админ-панели
router = Router()

# Включение всех подроутеров
router.include_router(themes.router)
router.include_router(authors.router)
router.include_router(teachers.router)
router.include_router(teachers_series.router)
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
    builder.add(InlineKeyboardButton(text="❓ Справка", callback_data="admin_help"))
    builder.add(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    builder.adjust(1)  # По одной кнопке в ряд

    await message.answer(
        "🛠️ <b>Административная панель</b>\n\n"
        "Выберите раздел для управления:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "admin_help")
@admin_required
async def admin_help(callback: CallbackQuery):
    """Показать справку по работе с админ-панелью"""
    help_text = """
❓ <b>Справка по работе с ботом</b>

<b>📋 Структура контента:</b>
📚 Тема → 📖 Книга → 🎧 Урок

<b>🎯 Основные сущности:</b>

<b>1. Темы</b> - категории для группировки книг
   Например: Акыда, Фикх, Хадисы

<b>2. Авторы</b> - авторы книг
   Например: Ибн Таймия, аш-Шатыри

<b>3. Преподаватели</b> - те, кто читает уроки
   Могут записать несколько циклов по одной книге

<b>4. Книги</b> - привязаны к теме и автору
   Могут быть без темы или без автора

<b>5. Уроки</b> - аудиозаписи
   • Привязаны к книге и преподавателю
   • Объединены в <b>серии</b> (год + название)
   • Пример: "2024 - мечеть", "2024 - фаида"

<b>🎧 Создание урока:</b>

<b>Шаги:</b>
1️⃣ Название урока
2️⃣ Описание (можно пропустить)
3️⃣ Год серии (2000-2050)
4️⃣ Название серии (место записи)
5️⃣ Выбор книги
6️⃣ Выбор преподавателя
7️⃣ Номер урока (или 0)
8️⃣ Длительность в минутах
9️⃣ Теги (можно пропустить)
🔟 Аудиофайл

<b>📁 Требования к аудиофайлам:</b>
✅ Форматы: MP3, M4A, OGG
✅ Размер: до 20 МБ
❌ Не поддерживаются: WAV, FLAC, WMA

<b>💡 Рекомендации:</b>
• Используйте MP3 (320kbps или 128kbps)
• M4A даёт лучшее сжатие
• Сжимайте большие файлы до 20 МБ

<b>🔄 Серии уроков:</b>
Один преподаватель может записать несколько
циклов по одной книге. Каждый цикл отличается
годом и названием серии.

<b>Пример:</b>
Книга "Три основы"
├─ 2024 - мечеть (10 уроков)
├─ 2024 - фаида (8 уроков)
└─ 2023 - марказ (12 уроков)

<b>🗂 Навигация по урокам:</b>
Уроки → Преподаватель → Тема → Книга → Серия → Урок

Это позволяет быстро найти нужный урок среди
сотен записей.
"""

    await callback.message.edit_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Назад в админ-панель", callback_data="admin_panel")
        ]])
    )
    await callback.answer()


@router.callback_query(F.data == "admin_panel")
@admin_required
async def admin_panel_callback(callback: CallbackQuery):
    """Вернуться в админ-панель через callback"""
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(text="📚 Управление темами", callback_data="admin_themes"))
    builder.add(InlineKeyboardButton(text="✍️ Управление авторами", callback_data="admin_authors"))
    builder.add(InlineKeyboardButton(text="👨‍🏫 Управление преподавателями", callback_data="admin_teachers"))
    builder.add(InlineKeyboardButton(text="📖 Управление книгами", callback_data="admin_books"))
    builder.add(InlineKeyboardButton(text="🎧 Управление уроками", callback_data="admin_lessons"))
    builder.add(InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users"))
    builder.add(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.add(InlineKeyboardButton(text="❓ Справка", callback_data="admin_help"))
    builder.add(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    builder.adjust(1)

    await callback.message.edit_text(
        "🛠️ <b>Административная панель</b>\n\n"
        "Выберите раздел для управления:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()
