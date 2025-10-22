"""
Административные обработчики - модульная структура
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required
from bot.utils.config import config

# Импорт роутеров из модулей
from . import themes, authors, teachers, teachers_series, books, lessons, users, stats, series, tests, feedbacks

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
router.include_router(series.router)
router.include_router(tests.router)
router.include_router(feedbacks.router)


@router.message(Command("admin"))
@admin_required
async def admin_panel(message: Message):
    """Показать административную панель"""
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(text="📚 Управление темами", callback_data="admin_themes"))
    builder.add(InlineKeyboardButton(text="✍️ Управление авторами", callback_data="admin_authors"))
    builder.add(InlineKeyboardButton(text="📖 Управление книгами", callback_data="admin_books"))
    builder.add(InlineKeyboardButton(text="👤 Управление преподавателями", callback_data="admin_teachers"))
    builder.add(InlineKeyboardButton(text="📁 Управление сериями", callback_data="admin_series"))
    builder.add(InlineKeyboardButton(text="🎧 Управление уроками", callback_data="admin_lessons"))
    builder.add(InlineKeyboardButton(text="🎓 Управление тестами", callback_data="admin_tests"))
    builder.add(InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users"))
    builder.add(InlineKeyboardButton(text="📨 Обращения", callback_data="admin_feedbacks"))
    builder.add(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.add(InlineKeyboardButton(text="ℹ️ Справка", callback_data="admin_help"))
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
ℹ️ <b>Справка по работе с ботом</b>

<b>📋 Структура контента:</b>
📚 Тема → 📖 Книга → 📁 Серия → 🎧 Урок

<b>🎯 Основные сущности:</b>

<b>1. Темы</b> - категории для группировки книг
   Например: Акыда, Фикх, Хадисы

<b>2. Авторы</b> - авторы книг
   Например: Ибн Таймия, аш-Шатыри

<b>3. Преподаватели</b> - те, кто читает уроки
   Могут записать несколько циклов по одной книге

<b>4. Книги</b> - привязаны к теме и автору
   Могут быть без темы или без автора

<b>5. Серии</b> - группы уроков
   • Создаются в разделе "📁 Управление сериями"
   • Привязаны к преподавателю
   • Могут быть привязаны к книге и теме
   • Состоят из года и названия
   • Пример: "2024 - мечеть", "2024 - фаида"

<b>6. Уроки</b> - аудиозаписи
   • Привязаны к серии
   • Наследуют преподавателя, книгу и тему от серии
   • Имеют номер урока, название и аудиофайл

<b>7. Тесты</b> - проверка знаний по сериям
   • Создаются в разделе "🎓 Управление тестами"
   • Привязаны к серии (один тест на серию)
   • Содержат вопросы с вариантами ответов
   • Каждый вопрос привязан к уроку серии
   • Настраиваются проходной балл и время на вопрос

<b>🎧 Создание урока (новая упрощённая система):</b>

<b>Подготовка:</b>
1️⃣ Создайте серию в "📁 Управление сериями"
   • Укажите преподавателя
   • Укажите год и название (например: 2024, мечеть)
   • По желанию: привяжите книгу и тему

<b>Добавление урока:</b>
2️⃣ Перейдите в "🎧 Управление уроками"
3️⃣ Выберите преподавателя
4️⃣ Выберите серию
5️⃣ Нажмите "➕ Добавить урок"
6️⃣ Введите номер урока (или 0)
7️⃣ Введите название урока
8️⃣ Введите описание (можно пропустить: -)
9️⃣ Загрузите аудиофайл

<b>📁 Требования к аудиофайлам:</b>
✅ Форматы: MP3, WAV, FLAC, M4A, OGG, AAC, WMA
✅ Размер: до 20 МБ (лимит Telegram Bot API)
⚡ Автоконвертация: Любой формат → MP3
⚡ Нормализация громкости: Автоматически

<b>🌐 Веб-конвертер для больших файлов (до 2 ГБ):</b>
🔗 URL: {web_url}
👤 Логин: <code>{web_login}</code>
🔐 Пароль: <code>{web_pass}</code>

Используйте веб-конвертер если файл больше 20 МБ.
После конвертации скачайте MP3 и отправьте боту.

<b>💡 Рекомендации:</b>
• Используйте MP3 64kbps для длинных уроков
• Уроки до 40 минут отлично влезают в 20 МБ
• Веб-конвертер автоматически подбирает битрейт

<b>🔄 Серии уроков:</b>
Один преподаватель может записать несколько
циклов по одной книге. Каждый цикл отличается
годом и названием серии.

<b>Пример:</b>
Книга "Три основы"
├─ 2024 - мечеть (10 уроков)
├─ 2024 - фаида (8 уроков)
└─ 2023 - марказ (12 уроков)

<b>🗂 Навигация по урокам (упрощённая):</b>
Управление уроками → Преподаватель → Серии → Уроки

Все серии преподавателя показываются сразу,
что позволяет быстро найти нужный урок.

<b>🎓 Создание теста:</b>

<b>Подготовка:</b>
1️⃣ Создайте серию с уроками
2️⃣ Перейдите в "🎓 Управление тестами"
3️⃣ Выберите преподавателя
4️⃣ Выберите серию (✅ = тест уже создан)
5️⃣ Создайте тест, укажите настройки

<b>Добавление вопросов:</b>
6️⃣ Нажмите "➕ Добавить вопрос"
7️⃣ Выберите урок из серии
8️⃣ Введите текст вопроса
9️⃣ Введите 4 варианта ответа
🔟 Укажите номер правильного ответа (1-4)
1️⃣1️⃣ По желанию: добавьте пояснение

<b>💡 О тестах:</b>
• Один тест на одну серию
• Вопросы группируются по урокам
• Проходной балл настраивается (по умолчанию 70%)
• Время на вопрос настраивается (по умолчанию 60 сек)
"""

    await callback.message.edit_text(
        help_text.format(
            web_url=config.web_converter_url,
            web_login=config.web_converter_login,
            web_pass=config.web_converter_password
        ),
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
    builder.add(InlineKeyboardButton(text="📖 Управление книгами", callback_data="admin_books"))
    builder.add(InlineKeyboardButton(text="👤 Управление преподавателями", callback_data="admin_teachers"))
    builder.add(InlineKeyboardButton(text="📁 Управление сериями", callback_data="admin_series"))
    builder.add(InlineKeyboardButton(text="🎧 Управление уроками", callback_data="admin_lessons"))
    builder.add(InlineKeyboardButton(text="🎓 Управление тестами", callback_data="admin_tests"))
    builder.add(InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users"))
    builder.add(InlineKeyboardButton(text="📨 Обращения", callback_data="admin_feedbacks"))
    builder.add(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.add(InlineKeyboardButton(text="ℹ️ Справка", callback_data="admin_help"))
    builder.add(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    builder.adjust(1)

    await callback.message.edit_text(
        "🛠️ <b>Административная панель</b>\n\n"
        "Выберите раздел для управления:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()
