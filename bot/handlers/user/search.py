from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.services.database_service import LessonService
from bot.keyboards.user import get_search_results_keyboard, get_main_keyboard
from bot.utils.decorators import user_required, user_required_callback

router = Router()


class SearchState(StatesGroup):
    search_query = State()


@router.callback_query(F.data == "search_lessons")
@user_required_callback
async def start_search(callback: CallbackQuery, state: FSMContext, user):
    """
    Начать поиск уроков
    """
    await callback.message.answer(
        "🔍 Введите ключевое слово для поиска уроков:\n\n"
        "Вы можете искать по названию урока, описанию или тегам."
    )
    await callback.answer()
    await state.set_state(SearchState.search_query)


@router.message(SearchState.search_query)
@user_required
async def process_search(message: Message, state: FSMContext, user):
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
async def new_search(callback: CallbackQuery, state: FSMContext, user):
    """
    Начать новый поиск
    """
    await callback.message.answer(
        "🔍 Введите ключевое слово для поиска уроков:\n\n"
        "Вы можете искать по названию урока, описанию или тегам."
    )
    await callback.answer()
    await state.set_state(SearchState.search_query)
