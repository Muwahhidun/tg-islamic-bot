"""
Клавиатуры для пользовательского интерфейса
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from bot.models import Theme, Book, Lesson


def get_main_keyboard() -> InlineKeyboardMarkup:
    """
    Главная инлайн-клавиатура для пользователя

    Returns:
        InlineKeyboardMarkup: Главная клавиатура
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📚 Список тем", callback_data="show_themes")],
            [InlineKeyboardButton(text="🔍 Поиск уроков", callback_data="search_lessons")],
            [InlineKeyboardButton(text="ℹ️ О проекте", callback_data="about_project")],
            [InlineKeyboardButton(text="🆔 Мой ID", callback_data="get_my_id")],
        ]
    )
    return keyboard


def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура для администратора
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура администратора
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Управление темами")],
            [KeyboardButton(text="✍️ Управление авторами книг")],
            [KeyboardButton(text="🎙️ Управление преподавателями")],
            [KeyboardButton(text="📖 Управление книгами")],
            [KeyboardButton(text="🎧 Управление уроками")],
            [KeyboardButton(text="👥 Управление пользователями")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="⬅️ Выйти из админки")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    return keyboard


def get_themes_keyboard(themes: list[Theme]) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком тем

    Args:
        themes: Список тем

    Returns:
        InlineKeyboardMarkup: Клавиатура с темами
    """
    keyboard = []

    for theme in themes:
        keyboard.append([InlineKeyboardButton(
            text=f"🔹 {theme.name}",
            callback_data=f"theme_{theme.id}"
        )])

    # Кнопка "Главное меню"
    keyboard.append([InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="main_menu"
    )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_books_keyboard(books: list[Book]) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком книг

    Args:
        books: Список книг

    Returns:
        InlineKeyboardMarkup: Клавиатура с книгами
    """
    keyboard = []

    for book in books:
        keyboard.append([InlineKeyboardButton(
            text=f"📖 {book.display_name}",
            callback_data=f"book_{book.id}"
        )])

    # Навигация
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Назад к темам",
        callback_data="back_to_themes"
    )])
    keyboard.append([InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="main_menu"
    )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lessons_keyboard(lessons: list[Lesson], theme_id: int = None) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком уроков

    Args:
        lessons: Список уроков
        theme_id: ID темы для кнопки "Назад к книгам"

    Returns:
        InlineKeyboardMarkup: Клавиатура с уроками
    """
    keyboard = []

    for lesson in lessons:
        title = lesson.display_title
        if lesson.duration_seconds:
            duration_formatted = lesson.formatted_duration
            title += f" ({duration_formatted})"

        keyboard.append([InlineKeyboardButton(
            text=f"🎧 {title}",
            callback_data=f"lesson_{lesson.id}"
        )])

    # Навигация
    if theme_id:
        keyboard.append([InlineKeyboardButton(
            text="⬅️ Назад к книгам",
            callback_data=f"theme_{theme_id}"
        )])
    else:
        keyboard.append([InlineKeyboardButton(
            text="⬅️ Назад к темам",
            callback_data="back_to_themes"
        )])
    keyboard.append([InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="main_menu"
    )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lesson_control_keyboard(lesson: Lesson) -> InlineKeyboardMarkup:
    """
    Клавиатура управления воспроизведением урока
    
    Args:
        lesson: Объект урока
        
    Returns:
        InlineKeyboardMarkup: Клавиатура управления
    """
    keyboard = []
    
    # Первая строка - навигация
    nav_buttons = []
    nav_buttons.append(InlineKeyboardButton(
        text="⬅️ Предыдущий",
        callback_data=f"prev_{lesson.id}"
    ))
    nav_buttons.append(InlineKeyboardButton(
        text="➡️ Следующий",
        callback_data=f"next_{lesson.id}"
    ))
    keyboard.append(nav_buttons)
    
    # Вторая строка - информация
    info_buttons = []
    if lesson.book and lesson.book.author:
        info_buttons.append(InlineKeyboardButton(
            text="ℹ️ Об авторе",
            callback_data=f"author_{lesson.book.author.id}"
        ))
    if lesson.teacher:
        info_buttons.append(InlineKeyboardButton(
            text="ℹ️ О преподавателе",
            callback_data=f"teacher_{lesson.teacher.id}"
        ))
    if info_buttons:
        keyboard.append(info_buttons)
    
    # Третья строка - возврат
    keyboard.append([InlineKeyboardButton(
        text="⬅️ К книге",
        callback_data=f"back_to_book_{lesson.book_id}"
    )])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_to_themes_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой возврата к темам
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой возврата
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ Назад к темам",
                callback_data="back_to_themes"
            )]
        ]
    )
    return keyboard


def get_back_to_books_keyboard(theme_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой возврата к книгам
    
    Args:
        theme_id: ID темы
        
    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой возврата
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ Назад к книгам",
                callback_data=f"back_to_books_{theme_id}"
            )]
        ]
    )
    return keyboard


def get_search_results_keyboard(lessons: list[Lesson], query: str) -> InlineKeyboardMarkup:
    """
    Клавиатура с результатами поиска

    Args:
        lessons: Список найденных уроков
        query: Поисковый запрос

    Returns:
        InlineKeyboardMarkup: Клавиатура с результатами
    """
    keyboard = []

    for lesson in lessons:
        title = lesson.display_title
        # Добавляем информацию о книге и теме
        title += f"\n📖 {lesson.book_title} | 🔹 {lesson.theme_name}"

        keyboard.append([InlineKeyboardButton(
            text=f"🎧 {title}",
            callback_data=f"lesson_{lesson.id}"
        )])

    # Навигация
    keyboard.append([InlineKeyboardButton(
        text="🔍 Новый поиск",
        callback_data="search_lessons"
    )])
    keyboard.append([InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="main_menu"
    )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура с кнопкой отмены
    
    Returns:
        ReplyKeyboardMarkup: Клавиатура с кнопкой отмены
    """
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения действия
    
    Returns:
        InlineKeyboardMarkup: Клавиатура подтверждения
    """
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="confirm_yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="confirm_no")
            ]
        ]
    )
    return keyboard