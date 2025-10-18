"""
Клавиатуры приложения
"""
from bot.keyboards.user import (
    get_main_keyboard,
    get_admin_keyboard,
    get_themes_keyboard,
    get_books_keyboard,
    get_lessons_keyboard,
    get_lesson_control_keyboard,
    get_back_to_themes_keyboard,
    get_back_to_books_keyboard,
    get_search_results_keyboard,
    get_cancel_keyboard,
    get_confirm_keyboard
)

__all__ = [
    "get_main_keyboard",
    "get_admin_keyboard",
    "get_themes_keyboard",
    "get_books_keyboard",
    "get_lessons_keyboard",
    "get_lesson_control_keyboard",
    "get_back_to_themes_keyboard",
    "get_back_to_books_keyboard",
    "get_search_results_keyboard",
    "get_cancel_keyboard",
    "get_confirm_keyboard"
]