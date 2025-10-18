from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.services.database_service import UserService
from bot.keyboards.user import get_main_keyboard

from . import themes, lessons, search

# Main router
router = Router()

# Include sub-routers
router.include_router(themes.router)
router.include_router(lessons.router)
router.include_router(search.router)


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handler for /start command with inline keyboard"""
    # Регистрация или получение пользователя
    user = await UserService.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    welcome_text = (
        f"🕌 Добро пожаловать, {message.from_user.first_name}!\n\n"
        "Здесь вы найдете аудио уроки по исламским наукам.\n\n"
        "Доступные темы:\n"
        "🔹 Акыда - Основы веры\n"
        "🔹 Сира - Жизнь пророка ﷺ\n"
        "🔹 Фикх - Исламское право\n"
        "🔹 Адаб - Исламский этикет\n\n"
        "Выберите действие из меню ниже:"
    )

    await message.answer(welcome_text, reply_markup=get_main_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handler for /help command with inline keyboard"""
    help_text = (
        "🕌 <b>Справка по боту</b>\n\n"
        "📚 <b>Основные команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/id - Узнать свой Telegram ID\n"
        "/help - Показать это справочное сообщение\n\n"
        "📖 <b>Как использовать:</b>\n"
        "1. Выберите интересующую тему\n"
        "2. Выберите книгу из списка\n"
        "3. Прослушайте уроки в порядке нумерации\n"
        "4. Используйте поиск для поиска уроков по ключевым словам\n\n"
        "🔍 <b>Поиск:</b>\n"
        "Поиск работает по названию урока, описанию и тегам\n\n"
        "💡 <b>Совет:</b>\n"
        "Используйте команду /id, чтобы узнать свой Telegram ID, "
        "если вы хотите получить права администратора или модератора."
    )

    await message.answer(help_text, reply_markup=get_main_keyboard())


@router.message(Command("id"))
async def cmd_id(message: Message):
    """Handler for /id command with inline keyboard"""
    user_id = message.from_user.id

    info_text = (
        f"🆔 <b>Ваш Telegram ID</b>\n\n"
        f"`{user_id}`\n\n"
        f"Вы можете сообщить этот ID администратору для получения прав доступа."
    )

    await message.answer(info_text, reply_markup=get_main_keyboard())


@router.callback_query(F.data == "get_my_id")
async def callback_get_my_id(callback: CallbackQuery):
    """Handler for callback 'get_my_id' (inline button)"""
    user_id = callback.from_user.id

    info_text = (
        f"🆔 <b>Ваш Telegram ID</b>\n\n"
        f"`{user_id}`\n\n"
        f"Вы можете сообщить этот ID администратору для получения прав доступа."
    )

    await callback.message.edit_text(info_text, reply_markup=get_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery):
    """Handler for callback 'main_menu' (returns to main menu)"""
    welcome_text = (
        "🕌 <b>Главное меню</b>\n\n"
        "Выберите действие:"
    )

    await callback.message.edit_text(welcome_text, reply_markup=get_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "about_project")
async def callback_about_project(callback: CallbackQuery):
    """Handler for callback 'about_project' (shows info about the project)"""
    about_text = (
        "🕌 <b>Об аудио боте для изучения исламских наук</b>\n\n"
        "Этот бот создан для удобного доступа к аудио урокам по исламским наукам.\n\n"
        "📚 <b>Доступные направления:</b>\n"
        "• Акыда - Основы веры и единобожия\n"
        "• Сира - Жизнь пророка Мухаммада ﷺ\n"
        "• Фикх - Исламское право и поклонение\n"
        "• Адаб - Исламский этикет и нравы\n\n"
        "🎧 <b>Возможности:</b>\n"
        "• Прослушивание аудио уроков\n"
        "• Поиск по ключевым словам\n"
        "• Скачивание уроков для офлайн-прослушивания\n\n"
        "🤲 <i>Пусть Allah примет этот труд и сделает его полезным для уммы!</i>"
    )

    await callback.message.edit_text(about_text, reply_markup=get_main_keyboard())
    await callback.answer()
