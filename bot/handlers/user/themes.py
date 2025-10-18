from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.services.database_service import ThemeService, BookService
from bot.keyboards.user import get_themes_keyboard, get_books_keyboard
from bot.utils.decorators import user_required_callback

router = Router()


@router.callback_query(F.data == "show_themes")
@user_required_callback
async def show_themes_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки 'Список тем' - показывает список доступных тем
    """
    # Очищаем состояние (например, если был режим поиска)
    await state.clear()

    themes = await ThemeService.get_all_active_themes()
    # Проверяем, есть ли книги без темы
    no_theme_books_count = await BookService.get_books_without_theme_count()

    text = "📚 Выберите тему:"
    keyboard = get_themes_keyboard(themes, no_theme_books_count)

    if not themes and no_theme_books_count == 0:
        text = "📭 Пока нет доступных тем"

    await callback.message.edit_text(text, reply_markup=keyboard if (themes or no_theme_books_count > 0) else None)
    await callback.answer()


@router.callback_query(F.data == "theme_none")
@user_required_callback
async def show_books_without_theme_handler(callback: CallbackQuery, state: FSMContext):
    """
    Показать книги без темы
    """
    # Очищаем состояние
    await state.clear()

    books = await BookService.get_books_by_theme(None)

    if not books:
        await callback.answer("📭 Нет книг без темы", show_alert=True)
        return

    text = f"📖 Без темы\n\nВыберите книгу:"
    keyboard = get_books_keyboard(books)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("theme_"))
@user_required_callback
async def show_books_handler(callback: CallbackQuery, state: FSMContext):
    """
    Показать книги выбранной темы
    """
    # Очищаем состояние
    await state.clear()

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


@router.callback_query(F.data == "back_to_themes")
@user_required_callback
async def back_to_themes_handler(callback: CallbackQuery, state: FSMContext):
    """
    Возврат к списку тем
    """
    # Очищаем состояние
    await state.clear()

    themes = await ThemeService.get_all_active_themes()
    # Проверяем, есть ли книги без темы
    no_theme_books_count = await BookService.get_books_without_theme_count()

    text = "📚 Выберите тему:"
    keyboard = get_themes_keyboard(themes, no_theme_books_count)

    if not themes and no_theme_books_count == 0:
        text = "📭 Пока нет доступных тем"

    await callback.message.edit_text(text, reply_markup=keyboard if (themes or no_theme_books_count > 0) else None)
    await callback.answer()
