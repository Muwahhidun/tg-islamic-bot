"""
Обработчики пользовательских команд
"""
from typing import Optional

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.services.database_service import (
    UserService, ThemeService, BookService, LessonService
)
from bot.keyboards.user import (
    get_main_keyboard, get_themes_keyboard, get_books_keyboard,
    get_lessons_keyboard, get_lesson_control_keyboard,
    get_back_to_themes_keyboard, get_back_to_books_keyboard,
    get_search_results_keyboard
)
from bot.utils.decorators import user_required, user_required_callback
from bot.utils.audio_utils import AudioUtils


# Создание роутера
router = Router()


class SearchState(StatesGroup):
    """Состояния для поиска"""
    search_query = State()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """
    Обработчик команды /start
    """
    # Регистрация или получение пользователя
    user = await UserService.get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Приветственное сообщение
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
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard()
    )


@router.message(Command("id"))
@user_required
async def cmd_get_id(message: types.Message, user):
    """
    Обработчик команды /id для получения Telegram ID
    """
    user_id = message.from_user.id
    
    info_text = (
        f"🆔 <b>Ваш Telegram ID</b>\n\n"
        f"`{user_id}`\n\n"
        f"Вы можете сообщить этот ID администратору для получения прав доступа."
    )
    
    await message.answer(info_text, reply_markup=get_main_keyboard())


@router.message(Command("help"))
@user_required
async def cmd_help(message: types.Message, user):
    """
    Обработчик команды /help
    """
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
        "4. Используйте поиск для finding уроков по ключевым словам\n\n"
        "🔍 <b>Поиск:</b>\n"
        "Поиск работает по названию урока, описанию и тегам\n\n"
        "💡 <b>Совет:</b>\n"
        "Используйте команду /id, чтобы узнать свой Telegram ID, "
        "если вы хотите получить права администратора или модератора."
    )
    
    await message.answer(help_text, reply_markup=get_main_keyboard())


@router.message(F.text == "📚 Список тем")
@user_required
async def show_themes(message: types.Message, user=None):
    """
    Показать список тем
    """
    themes = await ThemeService.get_all_active_themes()
    
    if not themes:
        await message.answer("📭 Пока нет доступных тем")
        return
    
    text = "📚 Выберите тему:"
    keyboard = get_themes_keyboard(themes)
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("theme_"))
@user_required_callback
async def show_books(callback: types.CallbackQuery):
    """
    Показать книги выбранной темы
    """
    theme_id = int(callback.data.split("_")[1])
    theme = await ThemeService.get_theme_by_id(theme_id)
    
    if not theme:
        await callback.answer("❌ Тема не найдена", show_alert=True)
        return
    
    books = await BookService.get_books_by_theme(theme_id)
    
    if not books:
        await callback.answer("📭 В этой теме пока нет книг", show_alert=True)
        return
    
    text = f"📖 Тема: {theme.name}\n\nВыберите книгу:"
    keyboard = get_books_keyboard(books)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("book_"))
@user_required_callback
async def show_lessons(callback: types.CallbackQuery):
    """
    Показать уроки выбранной книги
    """
    book_id = int(callback.data.split("_")[1])
    book = await BookService.get_book_by_id(book_id)
    
    if not book:
        await callback.answer("❌ Книга не найдена", show_alert=True)
        return
    
    lessons = await LessonService.get_lessons_by_book(book_id)
    
    if not lessons:
        await callback.answer("📭 В этой книге пока нет уроков", show_alert=True)
        return
    
    text = (
        f"📖 Книга: «{book.name}»\n"
        f"✍️ Автор: {book.author_info}\n\n"
        f"Список уроков ({len(lessons)}):"
    )
    keyboard = get_lessons_keyboard(lessons)
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("lesson_"))
@user_required_callback
async def play_lesson(callback: types.CallbackQuery):
    """
    Воспроизведение урока
    """
    lesson_id = int(callback.data.split("_")[1])
    lesson = await LessonService.get_lesson_by_id(lesson_id)
    
    if not lesson:
        await callback.answer("❌ Урок не найден", show_alert=True)
        return
    
    if not lesson.has_audio():
        await callback.answer("❌ Аудиофайл недоступен", show_alert=True)
        return
    
    # Проверка существования файла
    if not AudioUtils.file_exists(lesson.audio_path):
        await callback.answer("❌ Аудиофайл не найден", show_alert=True)
        return
    
    # Формирование описания урока
    caption = (
        f"🎧 {lesson.display_title}\n\n"
        f"📖 Книга: «{lesson.book_title}»\n"
        f"✍️ Автор: {lesson.book.author_info if lesson.book and lesson.book.author else 'Не указан'}\n"
        f"🎙️ Преподаватель: {lesson.teacher_name}\n"
        f"⏱️ Длительность: {lesson.formatted_duration}\n"
    )
    
    # Добавляем теги, если они есть
    if lesson.tags_list:
        tags_text = ", ".join(lesson.tags_list)
        caption += f"🏷️ Теги: {tags_text}\n"
    
    caption += "\n"
    
    if lesson.description:
        caption += f"📝 Описание: {lesson.description}"
    
    # Клавиатура управления
    keyboard = get_lesson_control_keyboard(lesson)
    
    try:
        # Отправка аудиофайла
        with open(lesson.audio_path, 'rb') as audio_file:
            await callback.message.answer_audio(
                audio=audio_file,
                title=lesson.title,
                caption=caption,
                reply_markup=keyboard
            )
    except Exception as e:
        await callback.answer(f"❌ Ошибка при загрузке аудио: {e}", show_alert=True)
        return
    
    await callback.answer()


@router.callback_query(F.data.startswith("prev_"))
@user_required_callback
async def previous_lesson(callback: types.CallbackQuery):
    """
    Перейти к предыдущему уроку
    """
    current_lesson_id = int(callback.data.split("_")[1])
    current_lesson = await LessonService.get_lesson_by_id(current_lesson_id)
    
    if not current_lesson:
        await callback.answer("❌ Урок не найден", show_alert=True)
        return
    
    # Получение всех уроков книги
    lessons = await LessonService.get_lessons_by_book(current_lesson.book_id)
    
    # Поиск текущего урока в списке
    current_index = None
    for i, lesson in enumerate(lessons):
        if lesson.id == current_lesson_id:
            current_index = i
            break
    
    if current_index is None or current_index == 0:
        await callback.answer("❌ Это первый урок в книге", show_alert=True)
        return
    
    # Переход к предыдущему уроку
    prev_lesson = lessons[current_index - 1]
    
    # Формирование callback_data для предыдущего урока
    callback.data = f"lesson_{prev_lesson.id}"
    await play_lesson(callback)


@router.callback_query(F.data.startswith("next_"))
@user_required_callback
async def next_lesson(callback: types.CallbackQuery):
    """
    Перейти к следующему уроку
    """
    current_lesson_id = int(callback.data.split("_")[1])
    current_lesson = await LessonService.get_lesson_by_id(current_lesson_id)
    
    if not current_lesson:
        await callback.answer("❌ Урок не найден", show_alert=True)
        return
    
    # Получение всех уроков книги
    lessons = await LessonService.get_lessons_by_book(current_lesson.book_id)
    
    # Поиск текущего урока в списке
    current_index = None
    for i, lesson in enumerate(lessons):
        if lesson.id == current_lesson_id:
            current_index = i
            break
    
    if current_index is None or current_index == len(lessons) - 1:
        await callback.answer("❌ Это последний урок в книге", show_alert=True)
        return
    
    # Переход к следующему уроку
    next_lesson = lessons[current_index + 1]
    
    # Формирование callback_data для следующего урока
    callback.data = f"lesson_{next_lesson.id}"
    await play_lesson(callback)


@router.callback_query(F.data.startswith("back_to_book_"))
@user_required_callback
async def back_to_book(callback: types.CallbackQuery):
    """
    Вернуться к книге
    """
    book_id = int(callback.data.split("_")[3])
    callback.data = f"book_{book_id}"
    await show_lessons(callback)


@router.callback_query(F.data == "back_to_themes")
@user_required_callback
async def back_to_themes(callback: types.CallbackQuery):
    """
    Вернуться к темам
    """
    await show_themes(callback.message)


@router.callback_query(F.data.startswith("back_to_books"))
@user_required_callback
async def back_to_books(callback: types.CallbackQuery):
    """
    Вернуться к книгам
    """
    parts = callback.data.split("_")
    if len(parts) > 3:  # back_to_books_theme_id имеет 4+ частей
        # Формат: back_to_books_theme_id или back_to_books_1
        theme_id = int(parts[-1])
        callback.data = f"theme_{theme_id}"
        await show_books(callback)
    else:
        # Общий возврат (просто "back_to_books")
        await show_themes(callback.message)


@router.message(F.text == "🔍 Поиск уроков")
@user_required
async def start_search(message: types.Message, state: FSMContext, user):
    """
    Начать поиск уроков
    """
    await message.answer(
        "🔍 Введите ключевое слово для поиска уроков:\n\n"
        "Вы можете искать по названию урока, описанию или тегам.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    await state.set_state(SearchState.search_query)


@router.message(SearchState.search_query)
@user_required
async def process_search(message: types.Message, state: FSMContext, user):
    """
    Обработка поискового запроса
    """
    query = message.text.strip()
    
    if len(query) < 2:
        await message.answer(
            "❌ Слишком короткий запрос. Введите хотя бы 2 символа.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    # Поиск уроков
    lessons = await LessonService.search_lessons(query)
    
    if not lessons:
        await message.answer(
            f"📭 По запросу «{query}» ничего не найдено.\n\n"
            "Попробуйте изменить запрос или выберите тему из меню.",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    text = f"🔍 Результаты поиска по запросу «{query}» ({len(lessons)}):"
    keyboard = get_search_results_keyboard(lessons, query)
    
    await message.answer(text, reply_markup=keyboard)
    await state.clear()


@router.callback_query(F.data == "new_search")
@user_required_callback
async def new_search(callback: types.CallbackQuery, state: FSMContext):
    """
    Начать новый поиск
    """
    await start_search(callback.message, state)


@router.message(F.text == "ℹ️ О проекте")
@user_required
async def about_project(message: types.Message, user):
    """
    Информация о проекте
    """
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
    
    await message.answer(about_text, reply_markup=get_main_keyboard())