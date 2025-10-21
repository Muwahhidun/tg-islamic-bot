from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.services.database_service import UserService
from bot.keyboards.user import get_main_keyboard
from bot.utils.decorators import is_user_admin

from . import themes, series, lessons, search, tests

# Main router
router = Router()

# Include sub-routers
router.include_router(themes.router)
router.include_router(series.router)  # Series must come before lessons (book_ handler)
router.include_router(lessons.router)
router.include_router(search.router)
router.include_router(tests.router)


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

    # Проверяем, является ли пользователь админом
    is_admin = await is_user_admin(message.from_user.id)

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

    await message.answer(welcome_text, reply_markup=get_main_keyboard(is_admin=is_admin))


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handler for /help command with inline keyboard"""
    # Проверяем, является ли пользователь админом
    is_admin = await is_user_admin(message.from_user.id)

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

    await message.answer(help_text, reply_markup=get_main_keyboard(is_admin=is_admin))


@router.message(Command("id"))
async def cmd_id(message: Message):
    """Handler for /id command with inline keyboard"""
    user_id = message.from_user.id

    # Проверяем, является ли пользователь админом
    is_admin = await is_user_admin(user_id)

    info_text = (
        f"🆔 <b>Ваш Telegram ID</b>\n\n"
        f"`{user_id}`\n\n"
        f"Вы можете сообщить этот ID администратору для получения прав доступа."
    )

    await message.answer(info_text, reply_markup=get_main_keyboard(is_admin=is_admin))


@router.callback_query(F.data == "get_my_id")
async def callback_get_my_id(callback: CallbackQuery, state: FSMContext):
    """Handler for callback 'get_my_id' (inline button)"""
    # Очищаем состояние
    await state.clear()

    user_id = callback.from_user.id

    # Проверяем, является ли пользователь админом
    is_admin = await is_user_admin(user_id)

    info_text = (
        f"🆔 <b>Ваш Telegram ID</b>\n\n"
        f"`{user_id}`\n\n"
        f"Вы можете сообщить этот ID администратору для получения прав доступа."
    )

    await callback.message.edit_text(info_text, reply_markup=get_main_keyboard(is_admin=is_admin))
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext):
    """Handler for callback 'main_menu' (returns to main menu)"""
    # Очищаем состояние
    await state.clear()

    # Проверяем, является ли пользователь админом
    is_admin = await is_user_admin(callback.from_user.id)

    welcome_text = (
        "🕌 <b>Главное меню</b>\n\n"
        "Выберите действие:"
    )

    await callback.message.edit_text(welcome_text, reply_markup=get_main_keyboard(is_admin=is_admin))
    await callback.answer()


@router.callback_query(F.data == "about_project")
async def callback_about_project(callback: CallbackQuery, state: FSMContext):
    """Handler for callback 'about_project' (shows info about the project)"""
    # Очищаем состояние
    await state.clear()

    # Проверяем, является ли пользователь админом
    is_admin = await is_user_admin(callback.from_user.id)

    about_text = (
        "بِسْمِ اللَّهِ الرَّحْمَـٰنِ الرَّحِيمِ\n\n"
        "🔊 <b>Muwahhid_bot — аудио-бот для изучения исламских наук</b>\n\n"
        "Бот создан, чтобы сделать изучение исламских наук удобным и доступным.\n"
        "Он помогает преподавателям собирать и систематизировать свои аудиоуроки,\n"
        "а обучающимся — легко находить, слушать и изучать их в любое время.\n\n"
        "📚 <b>Основные направления (и не только):</b>\n"
        "• Акыда — основы веры и единобожия\n"
        "• Сира — жизнь пророка Мухаммада ﷺ\n"
        "• Фикх — исламское право и поклонение\n"
        "• Адаб — исламский этикет и нравы\n"
        "(список направлений будет постепенно расширяться)\n\n"
        "🎧 <b>Возможности:</b>\n"
        "• Прослушивание аудиоуроков онлайн\n"
        "• Поиск по темам, лекторам и ключевым словам\n"
        "• Скачивание для офлайн-прослушивания\n"
        "• Закладки для сохранения нужных уроков\n"
        "• Тесты для проверки усвоенных знаний\n\n"
        "❗ Для замечаний, пожеланий, есть специальная кнопка для обратной связи с автором проекта.\n\n"
        "Пусть Аллах примет этот труд, сделает его полезным для уммы\n"
        "и причиной распространения полезных знаний!"
    )

    await callback.message.edit_text(about_text, reply_markup=get_main_keyboard(is_admin=is_admin))
    await callback.answer()
