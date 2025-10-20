"""
Обработчики управления тестами для администраторов
Новая структура: один тест на серию, вопросы привязаны к урокам
"""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.utils.decorators import admin_required
from bot.services.database_service import (
    get_all_tests,
    get_test_by_id,
    get_test_by_series,
    create_test,
    update_test,
    toggle_test_active,
    delete_test,
    get_questions_by_test,
    get_question_by_id,
    create_question,
    update_question,
    delete_question,
    get_all_lesson_teachers,
    get_series_by_teacher,
    get_series_by_id,
)

logger = logging.getLogger(__name__)

router = Router()


class TestStates(StatesGroup):
    """Состояния для создания/редактирования теста"""
    title = State()
    description = State()
    passing_score = State()
    time_per_question = State()
    edit_title = State()
    edit_description = State()
    edit_passing_score = State()
    edit_time = State()


class QuestionStates(StatesGroup):
    """Состояния для управления вопросами"""
    lesson_id = State()  # Выбор урока для вопроса
    question_text = State()
    option_1 = State()
    option_2 = State()
    option_3 = State()
    option_4 = State()
    correct_answer = State()
    explanation = State()


# ==================== ГЛАВНОЕ МЕНЮ ====================

@router.callback_query(F.data == "admin_tests")
@admin_required
async def tests_menu(callback: CallbackQuery):
    """Главное меню управления тестами"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📊 Все тесты", callback_data="tests_all"))
    builder.add(InlineKeyboardButton(text="👤 Преподаватели", callback_data="tests_teachers"))
    builder.add(InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_panel"))
    builder.adjust(1)

    await callback.message.edit_text(
        "📝 <b>Управление тестами</b>\n\n"
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


# ==================== ПРОСМОТР ТЕСТОВ ====================

@router.callback_query(F.data == "tests_all")
@admin_required
async def show_all_tests(callback: CallbackQuery):
    """Показать статистику по всем тестам"""
    tests = await get_all_tests()

    # Считаем статистику
    total_tests = len(tests)
    active_tests = len([t for t in tests if t.is_active])
    total_questions = sum(t.questions_count for t in tests)

    text = (
        "📊 <b>Статистика по тестам</b>\n\n"
        f"📝 Всего тестов: {total_tests}\n"
        f"✅ Активных: {active_tests}\n"
        f"❌ Неактивных: {total_tests - active_tests}\n"
        f"❓ Всего вопросов: {total_questions}\n"
    )

    if total_tests > 0:
        avg_questions = total_questions / total_tests
        text += f"📊 Среднее вопросов на тест: {avg_questions:.1f}\n"

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Назад", callback_data="admin_tests")
        ]])
    )
    await callback.answer()


@router.callback_query(F.data == "tests_teachers")
@admin_required
async def tests_teachers_list(callback: CallbackQuery):
    """Список преподавателей для управления тестами"""
    teachers = await get_all_lesson_teachers()

    if not teachers:
        await callback.message.edit_text(
            "❌ <b>Преподавателей нет</b>\n\n"
            "Сначала создайте преподавателей",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data="admin_tests")
            ]])
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for teacher in teachers:
        if teacher.is_active:
            builder.add(InlineKeyboardButton(
                text=f"👤 {teacher.name}",
                callback_data=f"tests_teacher_{teacher.id}"
            ))

    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_tests"))
    builder.adjust(1)

    await callback.message.edit_text(
        "👤 <b>Преподаватели</b>\n\n"
        "Выберите преподавателя:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_test_"))
@admin_required
async def toggle_test(callback: CallbackQuery):
    """Переключить активность теста"""
    test_id = int(callback.data.split("_")[2])
    test = await toggle_test_active(test_id)

    if not test:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    # Перенаправляем на просмотр серии (который покажет тест)
    teacher_id = test.teacher_id
    series_id = test.series_id

    class FakeCallback:
        def __init__(self, original_callback, new_data):
            self.message = original_callback.message
            self.data = new_data
            self.from_user = original_callback.from_user

        async def answer(self, *args, **kwargs):
            pass

    fake_callback = FakeCallback(callback, f"tests_series_{teacher_id}_{series_id}")
    await tests_series_view(fake_callback)
    await callback.answer("✅ Статус изменён")


@router.callback_query(F.data.startswith("delete_test_confirm_"))
@admin_required
async def delete_test_confirm(callback: CallbackQuery):
    """Подтверждение удаления теста"""
    test_id = int(callback.data.split("_")[3])
    test = await get_test_by_id(test_id)

    if not test:
        await callback.answer("❌ Тест не найден", show_alert=True)
        return

    text = (
        f"🗑 <b>Удаление теста</b>\n\n"
        f"Вы уверены, что хотите удалить тест?\n\n"
        f"📝 {test.title}\n"
        f"❓ Вопросов: {test.questions_count}\n\n"
        f"⚠️ Это действие нельзя отменить!"
    )

    # Получаем teacher_id и series_id для правильной навигации
    teacher_id = test.teacher_id
    series_id = test.series_id

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_test_{test_id}"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"tests_series_{teacher_id}_{series_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.regexp(r"^delete_test_\d+$"))
@admin_required
async def delete_test_handler(callback: CallbackQuery):
    """Удалить тест"""
    test_id = int(callback.data.split("_")[2])

    # Получаем тест до удаления, чтобы знать куда вернуться
    test = await get_test_by_id(test_id)
    if test:
        teacher_id = test.teacher_id
        series_id = test.series_id
    else:
        await callback.answer("❌ Тест не найден", show_alert=True)
        return

    success = await delete_test(test_id)

    if success:
        await callback.message.edit_text(
            "✅ <b>Тест удалён</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К серии", callback_data=f"tests_series_{teacher_id}_{series_id}")
            ]])
        )
        await callback.answer("✅ Тест удалён")
    else:
        await callback.answer("❌ Ошибка удаления", show_alert=True)


# ==================== РЕДАКТИРОВАНИЕ ТЕСТОВ ====================

@router.callback_query(F.data.regexp(r"^edit_test_\d+$"))
@admin_required
async def edit_test_menu(callback: CallbackQuery):
    """Меню редактирования теста"""
    test_id = int(callback.data.split("_")[2])
    test = await get_test_by_id(test_id)

    if not test:
        await callback.answer("❌ Тест не найден", show_alert=True)
        return

    # Формируем информацию
    info = f"✏️ <b>Редактирование теста</b>\n\n"
    info += f"📝 Название: {test.title}\n"
    info += f"📄 Описание: {test.description or 'не указано'}\n"
    info += f"✅ Проходной балл: {test.passing_score}%\n"
    info += f"⏱ Время на вопрос: {test.time_per_question_seconds} сек\n"
    info += f"📚 Серия: {test.series.display_name}\n"
    info += f"❓ Вопросов: {test.questions_count}\n"

    # Кнопки редактирования
    teacher_id = test.teacher_id
    series_id = test.series_id

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Название", callback_data=f"edit_test_title_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Описание", callback_data=f"edit_test_description_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Проходной балл", callback_data=f"edit_test_passing_score_{test_id}"))
    builder.add(InlineKeyboardButton(text="⏱ Время на вопрос", callback_data=f"edit_test_time_{test_id}"))
    builder.add(InlineKeyboardButton(text="🔙 К тесту", callback_data=f"tests_series_{teacher_id}_{series_id}"))
    builder.adjust(1)

    await callback.message.edit_text(info, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("edit_test_title_"))
@admin_required
async def edit_test_title_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование названия теста"""
    test_id = int(callback.data.split("_")[3])
    test = await get_test_by_id(test_id)

    if not test:
        await callback.answer("❌ Тест не найден", show_alert=True)
        return

    await state.update_data(
        test_id=test_id,
        edit_message_id=callback.message.message_id,
        edit_chat_id=callback.message.chat.id
    )

    await callback.message.edit_text(
        f"✏️ <b>Редактирование названия теста</b>\n\n"
        f"Текущее название: <b>{test.title}</b>\n\n"
        f"Введите новое название:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_test_{test_id}")
        ]])
    )
    await state.set_state(TestStates.edit_title)
    await callback.answer()


@router.message(TestStates.edit_title)
@admin_required
async def save_test_title(message: Message, state: FSMContext):
    """Сохранить новое название теста"""
    data = await state.get_data()
    test_id = data['test_id']

    try:
        await message.delete()
    except:
        pass

    # Обновляем тест
    test = await get_test_by_id(test_id)
    test.title = message.text
    await update_test(test)

    # Перезагружаем тест
    test = await get_test_by_id(test_id)

    # Формируем информацию для меню редактирования
    info = f"✏️ <b>Редактирование теста</b>\n\n"
    info += f"📝 Название: {test.title}\n"
    info += f"📄 Описание: {test.description or 'не указано'}\n"
    info += f"✅ Проходной балл: {test.passing_score}%\n"
    info += f"⏱ Время на вопрос: {test.time_per_question_seconds} сек\n"
    info += f"📚 Серия: {test.series.display_name}\n"
    info += f"❓ Вопросов: {test.questions_count}\n"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Название", callback_data=f"edit_test_title_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Описание", callback_data=f"edit_test_description_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Проходной балл", callback_data=f"edit_test_passing_score_{test_id}"))
    builder.add(InlineKeyboardButton(text="⏱ Время на вопрос", callback_data=f"edit_test_time_{test_id}"))
    builder.add(InlineKeyboardButton(text="🔙 К тесту", callback_data=f"tests_series_{test.teacher_id}_{test.series_id}"))
    builder.adjust(1)

    await message.bot.edit_message_text(
        chat_id=data['edit_chat_id'],
        message_id=data['edit_message_id'],
        text=info,
        reply_markup=builder.as_markup()
    )
    await state.clear()


@router.callback_query(F.data.startswith("edit_test_description_"))
@admin_required
async def edit_test_description_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование описания теста"""
    test_id = int(callback.data.split("_")[3])
    test = await get_test_by_id(test_id)

    if not test:
        await callback.answer("❌ Тест не найден", show_alert=True)
        return

    await state.update_data(
        test_id=test_id,
        edit_message_id=callback.message.message_id,
        edit_chat_id=callback.message.chat.id
    )

    await callback.message.edit_text(
        f"✏️ <b>Редактирование описания теста</b>\n\n"
        f"Текущее описание: {test.description or 'не указано'}\n\n"
        f"Введите новое описание:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить описание", callback_data=f"delete_test_description_{test_id}")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_test_{test_id}")]
        ])
    )
    await state.set_state(TestStates.edit_description)
    await callback.answer()


@router.callback_query(F.data.startswith("delete_test_description_"))
@admin_required
async def delete_test_description(callback: CallbackQuery, state: FSMContext):
    """Удалить описание теста"""
    test_id = int(callback.data.split("_")[3])
    test = await get_test_by_id(test_id)

    if not test:
        await callback.answer("❌ Тест не найден", show_alert=True)
        return

    test.description = None
    await update_test(test)
    test = await get_test_by_id(test_id)

    # Возвращаемся в меню редактирования
    info = f"✏️ <b>Редактирование теста</b>\n\n"
    info += f"📝 Название: {test.title}\n"
    info += f"📄 Описание: {test.description or 'не указано'}\n"
    info += f"✅ Проходной балл: {test.passing_score}%\n"
    info += f"⏱ Время на вопрос: {test.time_per_question_seconds} сек\n"
    info += f"📚 Серия: {test.series.display_name}\n"
    info += f"❓ Вопросов: {test.questions_count}\n"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Название", callback_data=f"edit_test_title_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Описание", callback_data=f"edit_test_description_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Проходной балл", callback_data=f"edit_test_passing_score_{test_id}"))
    builder.add(InlineKeyboardButton(text="⏱ Время на вопрос", callback_data=f"edit_test_time_{test_id}"))
    builder.add(InlineKeyboardButton(text="🔙 К тесту", callback_data=f"tests_series_{test.teacher_id}_{test.series_id}"))
    builder.adjust(1)

    await callback.message.edit_text(info, reply_markup=builder.as_markup())
    await state.clear()
    await callback.answer("✅ Описание удалено")


@router.message(TestStates.edit_description)
@admin_required
async def save_test_description(message: Message, state: FSMContext):
    """Сохранить новое описание теста"""
    data = await state.get_data()
    test_id = data['test_id']

    try:
        await message.delete()
    except:
        pass

    # Обновляем тест
    test = await get_test_by_id(test_id)
    test.description = message.text
    await update_test(test)

    # Перезагружаем тест
    test = await get_test_by_id(test_id)

    # Формируем информацию для меню редактирования
    info = f"✏️ <b>Редактирование теста</b>\n\n"
    info += f"📝 Название: {test.title}\n"
    info += f"📄 Описание: {test.description or 'не указано'}\n"
    info += f"✅ Проходной балл: {test.passing_score}%\n"
    info += f"⏱ Время на вопрос: {test.time_per_question_seconds} сек\n"
    info += f"📚 Серия: {test.series.display_name}\n"
    info += f"❓ Вопросов: {test.questions_count}\n"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Название", callback_data=f"edit_test_title_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Описание", callback_data=f"edit_test_description_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Проходной балл", callback_data=f"edit_test_passing_score_{test_id}"))
    builder.add(InlineKeyboardButton(text="⏱ Время на вопрос", callback_data=f"edit_test_time_{test_id}"))
    builder.add(InlineKeyboardButton(text="🔙 К тесту", callback_data=f"tests_series_{test.teacher_id}_{test.series_id}"))
    builder.adjust(1)

    await message.bot.edit_message_text(
        chat_id=data['edit_chat_id'],
        message_id=data['edit_message_id'],
        text=info,
        reply_markup=builder.as_markup()
    )
    await state.clear()


@router.callback_query(F.data.startswith("edit_test_passing_score_"))
@admin_required
async def edit_test_passing_score_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование проходного балла"""
    test_id = int(callback.data.split("_")[4])
    test = await get_test_by_id(test_id)

    if not test:
        await callback.answer("❌ Тест не найден", show_alert=True)
        return

    await state.update_data(
        test_id=test_id,
        edit_message_id=callback.message.message_id,
        edit_chat_id=callback.message.chat.id
    )

    await callback.message.edit_text(
        f"✏️ <b>Редактирование проходного балла</b>\n\n"
        f"Текущий проходной балл: <b>{test.passing_score}%</b>\n\n"
        f"Введите новый проходной балл (0-100):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_test_{test_id}")
        ]])
    )
    await state.set_state(TestStates.edit_passing_score)
    await callback.answer()


@router.message(TestStates.edit_passing_score)
@admin_required
async def save_test_passing_score(message: Message, state: FSMContext):
    """Сохранить новый проходной балл"""
    data = await state.get_data()
    test_id = data['test_id']

    try:
        await message.delete()
    except:
        pass

    # Валидация
    try:
        passing_score = int(message.text)
        if passing_score < 0 or passing_score > 100:
            raise ValueError()
    except:
        await message.bot.edit_message_text(
            chat_id=data['edit_chat_id'],
            message_id=data['edit_message_id'],
            text="❌ <b>Ошибка!</b>\n\nВведите число от 0 до 100:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_test_{test_id}")
            ]])
        )
        return

    # Обновляем тест
    test = await get_test_by_id(test_id)
    test.passing_score = passing_score
    await update_test(test)

    # Перезагружаем тест
    test = await get_test_by_id(test_id)

    # Формируем информацию для меню редактирования
    info = f"✏️ <b>Редактирование теста</b>\n\n"
    info += f"📝 Название: {test.title}\n"
    info += f"📄 Описание: {test.description or 'не указано'}\n"
    info += f"✅ Проходной балл: {test.passing_score}%\n"
    info += f"⏱ Время на вопрос: {test.time_per_question_seconds} сек\n"
    info += f"📚 Серия: {test.series.display_name}\n"
    info += f"❓ Вопросов: {test.questions_count}\n"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Название", callback_data=f"edit_test_title_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Описание", callback_data=f"edit_test_description_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Проходной балл", callback_data=f"edit_test_passing_score_{test_id}"))
    builder.add(InlineKeyboardButton(text="⏱ Время на вопрос", callback_data=f"edit_test_time_{test_id}"))
    builder.add(InlineKeyboardButton(text="🔙 К тесту", callback_data=f"tests_series_{test.teacher_id}_{test.series_id}"))
    builder.adjust(1)

    await message.bot.edit_message_text(
        chat_id=data['edit_chat_id'],
        message_id=data['edit_message_id'],
        text=info,
        reply_markup=builder.as_markup()
    )
    await state.clear()


@router.callback_query(F.data.startswith("edit_test_time_"))
@admin_required
async def edit_test_time_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование времени на вопрос"""
    test_id = int(callback.data.split("_")[3])
    test = await get_test_by_id(test_id)

    if not test:
        await callback.answer("❌ Тест не найден", show_alert=True)
        return

    await state.update_data(
        test_id=test_id,
        edit_message_id=callback.message.message_id,
        edit_chat_id=callback.message.chat.id
    )

    await callback.message.edit_text(
        f"⏱ <b>Редактирование времени на вопрос</b>\n\n"
        f"Текущее время: <b>{test.time_per_question_seconds} сек</b>\n\n"
        f"Введите новое время (10-300 секунд):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_test_{test_id}")
        ]])
    )
    await state.set_state(TestStates.edit_time)
    await callback.answer()


@router.message(TestStates.edit_time)
@admin_required
async def save_test_time(message: Message, state: FSMContext):
    """Сохранить новое время на вопрос"""
    data = await state.get_data()
    test_id = data['test_id']

    try:
        await message.delete()
    except:
        pass

    # Валидация
    try:
        time_per_question = int(message.text)
        if time_per_question < 10 or time_per_question > 300:
            raise ValueError()
    except:
        await message.bot.edit_message_text(
            chat_id=data['edit_chat_id'],
            message_id=data['edit_message_id'],
            text="❌ <b>Ошибка!</b>\n\nВведите число от 10 до 300 секунд:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_test_{test_id}")
            ]])
        )
        return

    # Обновляем тест
    test = await get_test_by_id(test_id)
    test.time_per_question_seconds = time_per_question
    await update_test(test)

    # Перезагружаем тест
    test = await get_test_by_id(test_id)

    # Формируем информацию для меню редактирования
    info = f"✏️ <b>Редактирование теста</b>\n\n"
    info += f"📝 Название: {test.title}\n"
    info += f"📄 Описание: {test.description or 'не указано'}\n"
    info += f"✅ Проходной балл: {test.passing_score}%\n"
    info += f"⏱ Время на вопрос: {test.time_per_question_seconds} сек\n"
    info += f"📚 Серия: {test.series.display_name}\n"
    info += f"❓ Вопросов: {test.questions_count}\n"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Название", callback_data=f"edit_test_title_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Описание", callback_data=f"edit_test_description_{test_id}"))
    builder.add(InlineKeyboardButton(text="✏️ Проходной балл", callback_data=f"edit_test_passing_score_{test_id}"))
    builder.add(InlineKeyboardButton(text="⏱ Время на вопрос", callback_data=f"edit_test_time_{test_id}"))
    builder.add(InlineKeyboardButton(text="🔙 К тесту", callback_data=f"tests_series_{test.teacher_id}_{test.series_id}"))
    builder.adjust(1)

    await message.bot.edit_message_text(
        chat_id=data['edit_chat_id'],
        message_id=data['edit_message_id'],
        text=info,
        reply_markup=builder.as_markup()
    )
    await state.clear()


# ==================== НАВИГАЦИЯ: ПРЕПОДАВАТЕЛЬ → СЕРИИ → ТЕСТ ====================

@router.callback_query(F.data.startswith("tests_teacher_"))
@admin_required
async def tests_teacher_series(callback: CallbackQuery):
    """Серии выбранного преподавателя"""
    teacher_id = int(callback.data.split("_")[2])

    series_list = await get_series_by_teacher(teacher_id)

    if not series_list:
        await callback.message.edit_text(
            "❌ У этого преподавателя нет серий",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data="tests_teachers")
            ]])
        )
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for series in series_list:
        # Проверяем есть ли уже тест для этой серии
        existing_test = await get_test_by_series(series.id)

        button_text = f"📚 {series.year} - {series.name}"
        if series.book_title:
            button_text += f" ({series.book_title})"

        if existing_test:
            button_text += " ✅"

        builder.add(InlineKeyboardButton(
            text=button_text,
            callback_data=f"tests_series_{teacher_id}_{series.id}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="tests_teachers"))
    builder.adjust(1)

    await callback.message.edit_text(
        "📚 <b>Серии преподавателя</b>\n\n"
        "Выберите серию:\n"
        "(✅ = тест уже создан)",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tests_series_"))
@admin_required
async def tests_series_view(callback: CallbackQuery):
    """Просмотр/создание теста для серии"""
    parts = callback.data.split("_")
    teacher_id = int(parts[2])
    series_id = int(parts[3])

    # Проверяем есть ли тест
    test = await get_test_by_series(series_id)

    if test:
        # Тест уже есть - показываем его
        info = test.full_info

        # Кнопки управления
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="📝 Вопросы", callback_data=f"test_questions_{test.id}"))
        builder.add(InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_test_{test.id}"))

        if test.is_active:
            builder.add(InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"toggle_test_{test.id}"))
        else:
            builder.add(InlineKeyboardButton(text="✅ Активировать", callback_data=f"toggle_test_{test.id}"))

        builder.add(InlineKeyboardButton(text="🗑 Удалить тест", callback_data=f"delete_test_confirm_{test.id}"))
        builder.add(InlineKeyboardButton(text="🔙 Назад к сериям", callback_data=f"tests_teacher_{teacher_id}"))
        builder.adjust(1)

        await callback.message.edit_text(info, reply_markup=builder.as_markup())
        await callback.answer()
    else:
        # Теста нет - предлагаем создать
        series = await get_series_by_id(series_id)

        if not series:
            await callback.answer("❌ Серия не найдена", show_alert=True)
            return

        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(
            text="➕ Создать тест",
            callback_data=f"create_test_for_series_{teacher_id}_{series_id}"
        ))
        builder.add(InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=f"tests_teacher_{teacher_id}"
        ))
        builder.adjust(1)

        await callback.message.edit_text(
            f"📝 <b>Тест для серии</b>\n\n"
            f"📚 Серия: {series.display_name}\n"
            f"👤 Преподаватель: {series.teacher.name if series.teacher else '???'}\n"
            f"🎧 Уроков: {len(series.lessons) if series.lessons else 0}\n\n"
            f"❌ Тест для этой серии ещё не создан.",
            reply_markup=builder.as_markup()
        )
        await callback.answer()


@router.callback_query(F.data.startswith("create_test_for_series_"))
@admin_required
async def create_test_for_series_start(callback: CallbackQuery, state: FSMContext):
    """Начать создание теста для серии"""
    parts = callback.data.split("_")
    teacher_id = int(parts[4])
    series_id = int(parts[5])

    # Сохраняем данные в state
    await state.update_data(
        teacher_id=teacher_id,
        series_id=series_id,
        create_message_id=callback.message.message_id,
        create_chat_id=callback.message.chat.id
    )

    await callback.message.edit_text(
        "📝 <b>Создание теста</b>\n\n"
        "Шаг 1: Введите название теста:\n\n"
        "Например: «Тест по Таухиду»",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"tests_series_{teacher_id}_{series_id}")
        ]])
    )
    await state.set_state(TestStates.title)
    await callback.answer()


# ==================== СОЗДАНИЕ ТЕСТА - FSM HANDLERS ====================

@router.message(TestStates.title)
@admin_required
async def save_test_title(message: Message, state: FSMContext):
    """Сохранить название теста"""
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    await state.update_data(title=message.text)

    await message.bot.edit_message_text(
        chat_id=data['create_chat_id'],
        message_id=data['create_message_id'],
        text="📝 <b>Создание теста</b>\n\n"
             "Шаг 2: Введите описание теста:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_test_description")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"tests_series_{data['teacher_id']}_{data['series_id']}")]
        ])
    )
    await state.set_state(TestStates.description)


@router.callback_query(F.data == "skip_test_description")
@admin_required
async def skip_test_description(callback: CallbackQuery, state: FSMContext):
    """Пропустить описание теста"""
    data = await state.get_data()

    await state.update_data(description=None)

    await callback.message.edit_text(
        text="📝 <b>Создание теста</b>\n\n"
             "Шаг 3: Введите проходной балл (в процентах):\n\n"
             "По умолчанию: 80%\n"
             "Допустимо: 0-100",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"tests_series_{data['teacher_id']}_{data['series_id']}")
        ]])
    )
    await state.set_state(TestStates.passing_score)
    await callback.answer()


@router.message(TestStates.description)
@admin_required
async def save_test_description(message: Message, state: FSMContext):
    """Сохранить описание теста"""
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    await state.update_data(description=message.text)

    await message.bot.edit_message_text(
        chat_id=data['create_chat_id'],
        message_id=data['create_message_id'],
        text="📝 <b>Создание теста</b>\n\n"
             "Шаг 3: Введите проходной балл (в процентах):\n\n"
             "По умолчанию: 80%\n"
             "Допустимо: 0-100",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"tests_series_{data['teacher_id']}_{data['series_id']}")
        ]])
    )
    await state.set_state(TestStates.passing_score)


@router.message(TestStates.passing_score)
@admin_required
async def save_test_passing_score(message: Message, state: FSMContext):
    """Сохранить проходной балл"""
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    try:
        passing_score = int(message.text)
        if not (0 <= passing_score <= 100):
            raise ValueError()
    except ValueError:
        await message.bot.edit_message_text(
            chat_id=data['create_chat_id'],
            message_id=data['create_message_id'],
            text="❌ <b>Ошибка!</b>\n\n"
                 "Проходной балл должен быть числом от 0 до 100.\n\n"
                 "Попробуйте ещё раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data=f"tests_series_{data['teacher_id']}_{data['series_id']}")
            ]])
        )
        return

    await state.update_data(passing_score=passing_score)

    await message.bot.edit_message_text(
        chat_id=data['create_chat_id'],
        message_id=data['create_message_id'],
        text="📝 <b>Создание теста</b>\n\n"
             "Шаг 4: Введите время на один вопрос (в секундах):\n\n"
             "По умолчанию: 30 секунд\n"
             "Допустимо: 10-300",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"tests_series_{data['teacher_id']}_{data['series_id']}")
        ]])
    )
    await state.set_state(TestStates.time_per_question)


@router.message(TestStates.time_per_question)
@admin_required
async def save_test_time_and_create(message: Message, state: FSMContext):
    """Сохранить время и создать тест"""
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    try:
        time_per_question = int(message.text)
        if not (10 <= time_per_question <= 300):
            raise ValueError()
    except ValueError:
        await message.bot.edit_message_text(
            chat_id=data['create_chat_id'],
            message_id=data['create_message_id'],
            text="❌ <b>Ошибка!</b>\n\n"
                 "Время должно быть числом от 10 до 300 секунд.\n\n"
                 "Попробуйте ещё раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Отмена", callback_data=f"tests_series_{data['teacher_id']}_{data['series_id']}")
            ]])
        )
        return

    # Создаём тест
    try:
        test = await create_test(
            title=data['title'],
            series_id=data['series_id'],
            teacher_id=data['teacher_id'],
            description=data.get('description'),
            passing_score=data['passing_score'],
            time_per_question_seconds=time_per_question
        )

        await message.bot.edit_message_text(
            chat_id=data['create_chat_id'],
            message_id=data['create_message_id'],
            text=f"✅ <b>Тест создан!</b>\n\n"
                 f"📝 {test.title}\n"
                 f"✅ Проходной балл: {test.passing_score}%\n"
                 f"⏱ Время на вопрос: {test.time_per_question_seconds} сек\n\n"
                 f"Теперь добавьте вопросы к тесту.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📝 Добавить вопросы", callback_data=f"test_questions_{test.id}"),
                InlineKeyboardButton(text="🔙 К серии", callback_data=f"tests_series_{data['teacher_id']}_{data['series_id']}")
            ]])
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка создания теста: {e}")
        await message.bot.edit_message_text(
            chat_id=data['create_chat_id'],
            message_id=data['create_message_id'],
            text=f"❌ <b>Ошибка создания теста!</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"tests_series_{data['teacher_id']}_{data['series_id']}")
            ]])
        )
        await state.clear()


# ==================== УПРАВЛЕНИЕ ВОПРОСАМИ ====================

@router.callback_query(F.data.startswith("test_questions_"))
@admin_required
async def test_questions_menu(callback: CallbackQuery):
    """Меню управления вопросами теста"""
    test_id = int(callback.data.split("_")[2])
    test = await get_test_by_id(test_id)

    if not test:
        await callback.answer("❌ Тест не найден", show_alert=True)
        return

    questions = await get_questions_by_test(test_id)

    # Группируем вопросы по урокам
    questions_by_lesson = {}
    for q in questions:
        lesson_id = q.lesson_id
        if lesson_id not in questions_by_lesson:
            questions_by_lesson[lesson_id] = []
        questions_by_lesson[lesson_id].append(q)

    # Формируем текст
    text = f"📝 <b>Тест: {test.title}</b>\n\n"
    text += f"📚 Серия: {test.series.display_name}\n"
    text += f"❓ Вопросов: {test.questions_count}\n\n"

    if questions:
        text += "═══════════════════\n\n"

        # Получаем уроки серии для правильного порядка
        series = await get_series_by_id(test.series_id)
        lessons = series.lessons if series else []

        for lesson in lessons:
            lesson_questions = questions_by_lesson.get(lesson.id, [])
            if lesson_questions:
                text += f"📚 <b>Урок {lesson.lesson_number}: {lesson.title}</b>\n"
                text += f"Вопросов: {len(lesson_questions)}\n\n"

        text += "═══════════════════\n"
    else:
        text += "❌ Вопросов пока нет.\n\n"

    # Кнопки
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="➕ Добавить вопрос", callback_data=f"add_question_{test_id}"))

    if questions:
        builder.add(InlineKeyboardButton(text="📋 Список вопросов", callback_data=f"list_questions_{test_id}"))

    builder.add(InlineKeyboardButton(text="🔙 К тесту", callback_data=f"tests_series_{test.teacher_id}_{test.series_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ==================== ДОБАВЛЕНИЕ ВОПРОСОВ ====================

@router.callback_query(F.data.startswith("add_question_"))
@admin_required
async def add_question_choose_lesson(callback: CallbackQuery, state: FSMContext):
    """Выбор урока для вопроса"""
    test_id = int(callback.data.split("_")[2])
    test = await get_test_by_id(test_id)

    if not test:
        await callback.answer("❌ Тест не найден", show_alert=True)
        return

    # Получаем уроки серии
    series = await get_series_by_id(test.series_id)
    if not series or not series.lessons:
        await callback.message.edit_text(
            "❌ <b>Ошибка!</b>\n\n"
            "В серии нет уроков.\n"
            "Сначала добавьте уроки к серии.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"test_questions_{test_id}")
            ]])
        )
        await callback.answer()
        return

    # Показываем список уроков
    builder = InlineKeyboardBuilder()
    for lesson in series.lessons:
        builder.add(InlineKeyboardButton(
            text=f"📚 Урок {lesson.lesson_number}: {lesson.title}",
            callback_data=f"add_q_lesson_{test_id}_{lesson.id}"
        ))

    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"test_questions_{test_id}"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"📝 <b>Добавление вопроса</b>\n\n"
        f"Выберите урок, к которому относится вопрос:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add_q_lesson_"))
@admin_required
async def add_question_start_input(callback: CallbackQuery, state: FSMContext):
    """Начать ввод вопроса"""
    parts = callback.data.split("_")
    test_id = int(parts[3])
    lesson_id = int(parts[4])

    # Сохраняем данные
    await state.update_data(
        test_id=test_id,
        lesson_id=lesson_id,
        question_message_id=callback.message.message_id,
        question_chat_id=callback.message.chat.id
    )

    await callback.message.edit_text(
        "📝 <b>Добавление вопроса</b>\n\n"
        "Шаг 1/7: Введите текст вопроса:\n\n"
        "Например: «Что такое Таухид?»",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"test_questions_{test_id}")
        ]])
    )
    await state.set_state(QuestionStates.question_text)
    await callback.answer()


# ==================== FSM HANDLERS ДЛЯ ДОБАВЛЕНИЯ ВОПРОСА ====================

@router.message(QuestionStates.question_text)
@admin_required
async def save_question_text(message: Message, state: FSMContext):
    """Сохранить текст вопроса"""
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    await state.update_data(question_text=message.text)

    await message.bot.edit_message_text(
        chat_id=data['question_chat_id'],
        message_id=data['question_message_id'],
        text="📝 <b>Добавление вопроса</b>\n\n"
             "Шаг 2/7: Введите вариант ответа №1:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"test_questions_{data['test_id']}")
        ]])
    )
    await state.set_state(QuestionStates.option_1)


@router.message(QuestionStates.option_1)
@admin_required
async def save_option_1(message: Message, state: FSMContext):
    """Сохранить вариант 1"""
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    await state.update_data(option_1=message.text)

    await message.bot.edit_message_text(
        chat_id=data['question_chat_id'],
        message_id=data['question_message_id'],
        text="📝 <b>Добавление вопроса</b>\n\n"
             "Шаг 3/7: Введите вариант ответа №2:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"test_questions_{data['test_id']}")
        ]])
    )
    await state.set_state(QuestionStates.option_2)


@router.message(QuestionStates.option_2)
@admin_required
async def save_option_2(message: Message, state: FSMContext):
    """Сохранить вариант 2"""
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    await state.update_data(option_2=message.text)

    await message.bot.edit_message_text(
        chat_id=data['question_chat_id'],
        message_id=data['question_message_id'],
        text="📝 <b>Добавление вопроса</b>\n\n"
             "Шаг 4/7: Введите вариант ответа №3:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"test_questions_{data['test_id']}")
        ]])
    )
    await state.set_state(QuestionStates.option_3)


@router.message(QuestionStates.option_3)
@admin_required
async def save_option_3(message: Message, state: FSMContext):
    """Сохранить вариант 3"""
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    await state.update_data(option_3=message.text)

    await message.bot.edit_message_text(
        chat_id=data['question_chat_id'],
        message_id=data['question_message_id'],
        text="📝 <b>Добавление вопроса</b>\n\n"
             "Шаг 5/7: Введите вариант ответа №4:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"test_questions_{data['test_id']}")
        ]])
    )
    await state.set_state(QuestionStates.option_4)


@router.message(QuestionStates.option_4)
@admin_required
async def save_option_4(message: Message, state: FSMContext):
    """Сохранить вариант 4 и показать выбор правильного ответа"""
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    await state.update_data(option_4=message.text)

    # Показываем все варианты для выбора правильного
    text = (
        "📝 <b>Добавление вопроса</b>\n\n"
        f"Вопрос: {data['question_text']}\n\n"
        f"1️⃣ {data['option_1']}\n"
        f"2️⃣ {data['option_2']}\n"
        f"3️⃣ {data['option_3']}\n"
        f"4️⃣ {message.text}\n\n"
        "Шаг 6/7: Какой вариант правильный?"
    )

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="1️⃣", callback_data=f"q_correct_1_{data['test_id']}"))
    builder.add(InlineKeyboardButton(text="2️⃣", callback_data=f"q_correct_2_{data['test_id']}"))
    builder.add(InlineKeyboardButton(text="3️⃣", callback_data=f"q_correct_3_{data['test_id']}"))
    builder.add(InlineKeyboardButton(text="4️⃣", callback_data=f"q_correct_4_{data['test_id']}"))
    builder.add(InlineKeyboardButton(text="🔙 Отмена", callback_data=f"test_questions_{data['test_id']}"))
    builder.adjust(4, 1)

    await message.bot.edit_message_text(
        chat_id=data['question_chat_id'],
        message_id=data['question_message_id'],
        text=text,
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.regexp(r"^q_correct_\d+_\d+$"))
@admin_required
async def save_correct_answer(callback: CallbackQuery, state: FSMContext):
    """Сохранить правильный ответ"""
    parts = callback.data.split("_")
    correct_num = int(parts[2])
    test_id = int(parts[3])

    data = await state.get_data()

    # Сохраняем индекс правильного ответа (0-3)
    await state.update_data(correct_answer=correct_num - 1)

    await callback.message.edit_text(
        "📝 <b>Добавление вопроса</b>\n\n"
        "Шаг 7/7: Введите пояснение к ответу:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data=f"skip_question_explanation")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"test_questions_{test_id}")]
        ])
    )
    await state.set_state(QuestionStates.explanation)
    await callback.answer()


@router.callback_query(F.data == "skip_question_explanation")
@admin_required
async def skip_question_explanation(callback: CallbackQuery, state: FSMContext):
    """Пропустить пояснение и создать вопрос"""
    data = await state.get_data()

    # Создаём вопрос без пояснения
    try:
        options = [
            data['option_1'],
            data['option_2'],
            data['option_3'],
            data['option_4']
        ]

        question = await create_question(
            test_id=data['test_id'],
            lesson_id=data['lesson_id'],
            question_text=data['question_text'],
            options=options,
            correct_answer_index=data['correct_answer'],
            explanation=None
        )

        # Получаем обновлённый тест
        test = await get_test_by_id(data['test_id'])

        await callback.message.edit_text(
            text=f"✅ <b>Вопрос добавлен!</b>\n\n"
                 f"📝 {data['question_text']}\n"
                 f"✅ Правильный ответ: вариант {data['correct_answer'] + 1}\n\n"
                 f"Всего вопросов в тесте: {test.questions_count}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="➕ Добавить ещё вопрос", callback_data=f"add_question_{data['test_id']}"),
                InlineKeyboardButton(text="📋 Список вопросов", callback_data=f"list_questions_{data['test_id']}"),
                InlineKeyboardButton(text="🔙 К тесту", callback_data=f"test_questions_{data['test_id']}")
            ]])
        )
        await state.clear()
        await callback.answer("✅ Вопрос добавлен")

    except Exception as e:
        logger.error(f"Ошибка создания вопроса: {e}")
        await callback.message.edit_text(
            text=f"❌ <b>Ошибка создания вопроса!</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"test_questions_{data['test_id']}")
            ]])
        )
        await state.clear()
        await callback.answer("❌ Ошибка", show_alert=True)


@router.message(QuestionStates.explanation)
@admin_required
async def save_explanation_and_create(message: Message, state: FSMContext):
    """Сохранить пояснение и создать вопрос"""
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    explanation = message.text

    # Создаём вопрос
    try:
        options = [
            data['option_1'],
            data['option_2'],
            data['option_3'],
            data['option_4']
        ]

        question = await create_question(
            test_id=data['test_id'],
            lesson_id=data['lesson_id'],
            question_text=data['question_text'],
            options=options,
            correct_answer_index=data['correct_answer'],
            explanation=explanation
        )

        # Получаем обновлённый тест
        test = await get_test_by_id(data['test_id'])

        await message.bot.edit_message_text(
            chat_id=data['question_chat_id'],
            message_id=data['question_message_id'],
            text=f"✅ <b>Вопрос добавлен!</b>\n\n"
                 f"📝 {data['question_text']}\n"
                 f"✅ Правильный ответ: вариант {data['correct_answer'] + 1}\n\n"
                 f"Всего вопросов в тесте: {test.questions_count}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="➕ Добавить ещё вопрос", callback_data=f"add_question_{data['test_id']}"),
                InlineKeyboardButton(text="📋 Список вопросов", callback_data=f"list_questions_{data['test_id']}"),
                InlineKeyboardButton(text="🔙 К тесту", callback_data=f"test_questions_{data['test_id']}")
            ]])
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка создания вопроса: {e}")
        await message.bot.edit_message_text(
            chat_id=data['question_chat_id'],
            message_id=data['question_message_id'],
            text=f"❌ <b>Ошибка создания вопроса!</b>\n\n{str(e)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"test_questions_{data['test_id']}")
            ]])
        )
        await state.clear()


# ==================== ПРОСМОТР СПИСКА ВОПРОСОВ ====================

@router.callback_query(F.data.startswith("list_questions_"))
@admin_required
async def list_questions(callback: CallbackQuery):
    """Показать список всех вопросов с детальной информацией"""
    test_id = int(callback.data.split("_")[2])
    test = await get_test_by_id(test_id)

    if not test:
        await callback.answer("❌ Тест не найден", show_alert=True)
        return

    questions = await get_questions_by_test(test_id)

    if not questions:
        await callback.message.edit_text(
            "❌ <b>Вопросов нет</b>\n\n"
            "Добавьте вопросы к тесту.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="➕ Добавить вопрос", callback_data=f"add_question_{test_id}"),
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"test_questions_{test_id}")
            ]])
        )
        await callback.answer()
        return

    # Группируем по урокам
    series = await get_series_by_id(test.series_id)
    lessons = series.lessons if series else []

    questions_by_lesson = {}
    for q in questions:
        if q.lesson_id not in questions_by_lesson:
            questions_by_lesson[q.lesson_id] = []
        questions_by_lesson[q.lesson_id].append(q)

    # Формируем текст
    text = f"📝 <b>{test.title}</b>\n"
    text += f"📚 {test.series.display_name}\n"
    text += f"❓ Всего вопросов: {test.questions_count}\n\n"
    text += "═══════════════════\n\n"

    builder = InlineKeyboardBuilder()

    for lesson in lessons:
        lesson_questions = questions_by_lesson.get(lesson.id, [])
        if lesson_questions:
            text += f"📚 <b>Урок {lesson.lesson_number}: {lesson.title}</b>\n\n"

            for q in lesson_questions:
                text += f"❓ <b>Вопрос #{q.id}</b>\n"
                text += f"{q.question_text}\n"
                text += f"✅ Правильный: вариант {q.correct_answer_index + 1}\n"

                builder.add(InlineKeyboardButton(
                    text=f"✏️ #{q.id}",
                    callback_data=f"edit_question_{q.id}"
                ))
                builder.add(InlineKeyboardButton(
                    text=f"🗑 #{q.id}",
                    callback_data=f"delete_q_confirm_{q.id}"
                ))

            text += "\n"

    builder.add(InlineKeyboardButton(text="➕ Добавить вопрос", callback_data=f"add_question_{test_id}"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"test_questions_{test_id}"))
    builder.adjust(2, 2, 1, 1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ==================== УДАЛЕНИЕ ВОПРОСОВ ====================

@router.callback_query(F.data.startswith("delete_q_confirm_"))
@admin_required
async def delete_question_confirm(callback: CallbackQuery):
    """Подтверждение удаления вопроса"""
    question_id = int(callback.data.split("_")[3])
    question = await get_question_by_id(question_id)

    if not question:
        await callback.answer("❌ Вопрос не найден", show_alert=True)
        return

    text = (
        f"🗑 <b>Удаление вопроса</b>\n\n"
        f"Вы уверены, что хотите удалить этот вопрос?\n\n"
        f"❓ {question.question_text}\n\n"
        f"⚠️ Это действие нельзя отменить!"
    )

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"delete_q_{question_id}"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"list_questions_{question.test_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("delete_q_") & ~F.data.contains("confirm"))
@admin_required
async def delete_question_handler(callback: CallbackQuery):
    """Удалить вопрос"""
    question_id = int(callback.data.split("_")[2])
    question = await get_question_by_id(question_id)

    if not question:
        await callback.answer("❌ Вопрос не найден", show_alert=True)
        return

    test_id = question.test_id
    success = await delete_question(question_id)

    if success:
        await callback.message.edit_text(
            "✅ <b>Вопрос удалён</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📋 К списку", callback_data=f"list_questions_{test_id}"),
                InlineKeyboardButton(text="🔙 К тесту", callback_data=f"test_questions_{test_id}")
            ]])
        )
        await callback.answer("✅ Вопрос удалён")
    else:
        await callback.answer("❌ Ошибка удаления", show_alert=True)


# ==================== ПРОСМОТР ВОПРОСА ====================

@router.callback_query(F.data.startswith("edit_question_"))
@admin_required
async def view_question_details(callback: CallbackQuery):
    """Просмотр детальной информации о вопросе"""
    question_id = int(callback.data.split("_")[2])
    question = await get_question_by_id(question_id)

    if not question:
        await callback.answer("❌ Вопрос не найден", show_alert=True)
        return

    # Формируем информацию о вопросе
    text = f"📝 <b>Вопрос #{question_id}</b>\n\n"
    text += f"❓ <b>Текст:</b>\n{question.question_text}\n\n"
    text += "<b>Варианты ответа:</b>\n"

    for i, option in enumerate(question.options_list, 1):
        marker = "✅" if i - 1 == question.correct_answer_index else "  "
        text += f"{i}. {marker} {option}\n"

    if question.explanation:
        text += f"\n💡 <b>Пояснение:</b>\n{question.explanation}"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🗑 Удалить вопрос", callback_data=f"delete_q_confirm_{question_id}"))
    builder.add(InlineKeyboardButton(text="🔙 К списку", callback_data=f"list_questions_{question.test_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
