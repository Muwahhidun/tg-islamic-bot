"""
Клавиатуры для пользовательского интерфейса
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from bot.models import Theme, Book, Lesson, LessonSeries


def get_main_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Главная инлайн-клавиатура для пользователя

    Args:
        is_admin: Является ли пользователь администратором

    Returns:
        InlineKeyboardMarkup: Главная клавиатура
    """
    buttons = [
        [InlineKeyboardButton(text="📚 Список тем", callback_data="show_themes")],
        [InlineKeyboardButton(text="📌 Закладки", callback_data="bookmarks")],
        [InlineKeyboardButton(text="🔍 Поиск уроков", callback_data="search_lessons")],
        [InlineKeyboardButton(text="ℹ️ О проекте", callback_data="about_project")],
        [InlineKeyboardButton(text="🆔 Мой ID", callback_data="get_my_id")],
    ]

    # Добавляем кнопку администрирования только для админов
    if is_admin:
        buttons.append([InlineKeyboardButton(text="🛠️ Администрирование", callback_data="admin_panel")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
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


def get_themes_keyboard(themes: list[Theme], no_theme_books_count: int = 0) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком тем

    Args:
        themes: Список тем
        no_theme_books_count: Количество книг без темы

    Returns:
        InlineKeyboardMarkup: Клавиатура с темами
    """
    keyboard = []

    for theme in themes:
        keyboard.append([InlineKeyboardButton(
            text=f"🔹 {theme.name}",
            callback_data=f"theme_{theme.id}"
        )])

    # Добавляем виртуальную категорию "Без темы", если есть книги без темы
    if no_theme_books_count > 0:
        keyboard.append([InlineKeyboardButton(
            text=f"📂 Без темы ({no_theme_books_count})",
            callback_data="theme_none"
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


def get_series_keyboard(series_list: list[LessonSeries], book_id: int) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком серий книги

    Args:
        series_list: Список серий
        book_id: ID книги для кнопки "Назад"

    Returns:
        InlineKeyboardMarkup: Клавиатура с сериями
    """
    keyboard = []

    for series in series_list:
        # Показываем год, название и количество уроков
        lessons_count = series.active_lessons_count
        text = f"📁 {series.year} - {series.name} ({lessons_count} уроков)"
        keyboard.append([InlineKeyboardButton(
            text=text,
            callback_data=f"series_{series.id}"
        )])

    # Навигация
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Назад к книгам",
        callback_data=f"theme_{book_id}"  # Возврат к теме покажет книги
    )])
    keyboard.append([InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="main_menu"
    )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_series_menu_keyboard(series_id: int, has_test: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура меню серии (Уроки / Общий тест / Назад)

    Args:
        series_id: ID серии
        has_test: Есть ли тест для серии

    Returns:
        InlineKeyboardMarkup: Клавиатура меню серии
    """
    keyboard = []

    # Кнопка "Уроки"
    keyboard.append([InlineKeyboardButton(
        text="🎧 Уроки",
        callback_data=f"series_lessons_{series_id}"
    )])

    # Кнопка "Общий тест" (если тест существует)
    if has_test:
        keyboard.append([InlineKeyboardButton(
            text="🎓 Общий тест",
            callback_data=f"general_test_{series_id}"
        )])

    # Кнопка "Назад"
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Назад к сериям",
        callback_data=f"back_to_series_list"
    )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lessons_keyboard(lessons: list[Lesson], series_id: int, has_tests: dict = None) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком уроков серии (с кнопками тестов под каждым уроком)

    Args:
        lessons: Список уроков
        series_id: ID серии для кнопки "Назад"
        has_tests: Словарь {lesson_id: bool} - есть ли тест для урока

    Returns:
        InlineKeyboardMarkup: Клавиатура с уроками и тестами
    """
    keyboard = []
    has_tests = has_tests or {}

    for lesson in lessons:
        title = lesson.display_title
        if lesson.duration_seconds:
            duration_formatted = lesson.formatted_duration
            title += f" ({duration_formatted})"

        # Кнопка урока
        keyboard.append([InlineKeyboardButton(
            text=f"🎧 {title}",
            callback_data=f"lesson_{lesson.id}"
        )])

        # Кнопка теста под уроком (если тест существует)
        if has_tests.get(lesson.id, False):
            keyboard.append([InlineKeyboardButton(
                text=f"🎓 Тест по уроку {lesson.lesson_number}",
                callback_data=f"lesson_test_{lesson.id}"
            )])

    # Навигация
    keyboard.append([InlineKeyboardButton(
        text="⬅️ Назад к серии",
        callback_data=f"series_{series_id}"
    )])
    keyboard.append([InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="main_menu"
    )])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lesson_control_keyboard(lesson: Lesson, has_test: bool = False, has_bookmark: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура управления воспроизведением урока

    Args:
        lesson: Объект урока
        has_test: Есть ли тест для серии урока
        has_bookmark: Есть ли закладка на этот урок

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

    # Следующая строка - информация о книге и авторе (горизонтально)
    book_author_buttons = []
    if lesson.book:
        book_author_buttons.append(InlineKeyboardButton(
            text="ℹ️ О книге",
            callback_data=f"book_info_{lesson.book.id}"
        ))
    if lesson.book and lesson.book.author:
        book_author_buttons.append(InlineKeyboardButton(
            text="ℹ️ Об авторе",
            callback_data=f"author_{lesson.book.author.id}"
        ))
    if book_author_buttons:
        keyboard.append(book_author_buttons)

    # Третья строка - информация о преподавателе
    if lesson.teacher:
        keyboard.append([InlineKeyboardButton(
            text="ℹ️ О преподавателе",
            callback_data=f"teacher_{lesson.teacher.id}"
        )])

    # Кнопка теста (если есть)
    if has_test:
        keyboard.append([InlineKeyboardButton(
            text="🎓 Пройти тест по уроку",
            callback_data=f"lesson_test_{lesson.id}"
        )])

    # Кнопка закладки (после теста)
    if has_bookmark:
        keyboard.append([InlineKeyboardButton(
            text="➖ В закладках",
            callback_data=f"remove_bookmark_{lesson.id}"
        )])
    else:
        keyboard.append([InlineKeyboardButton(
            text="➕ Добавить в закладки",
            callback_data=f"add_bookmark_{lesson.id}"
        )])

    # Последняя строка - возврат
    keyboard.append([InlineKeyboardButton(
        text="⬅️ К урокам",
        callback_data=f"back_to_series_lessons_{lesson.series_id}"
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