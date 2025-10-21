"""
Обработчики для прохождения тестов пользователями
"""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.utils.decorators import user_required_callback
from bot.services.database_service import (
    get_test_by_series,
    get_questions_by_lesson,
    get_questions_by_test,
    get_question_by_id,
    create_attempt,
    get_best_attempt,
    get_series_by_id,
)

logger = logging.getLogger(__name__)

router = Router()


class TestStates(StatesGroup):
    """Состояния для прохождения теста"""
    in_progress = State()
    current_question = State()


# ==================== ПОКАЗ ДОСТУПНЫХ ТЕСТОВ ====================

@router.callback_query(F.data.startswith("test_after_lesson_"))
@user_required_callback
async def show_test_after_lesson(callback: CallbackQuery, state: FSMContext):
    """Показать тест после прослушивания урока"""
    lesson_id = int(callback.data.split("_")[3])

    # Получаем урок и его серию
    from bot.services.database_service import get_lesson_by_id
    lesson = await get_lesson_by_id(lesson_id)

    if not lesson or not lesson.series_id:
        await callback.answer("❌ Урок не найден", show_alert=True)
        return

    # Получаем тест для серии
    test = await get_test_by_series(lesson.series_id)

    if not test or not test.is_active:
        text = "🎓 <b>Тест</b>\n\n❌ Для этого урока пока нет теста."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Назад к уроку", callback_data=f"lesson_{lesson_id}")
        ]])

        # ПАТТЕРН ОДНОГО ОКНА: проверяем тип сообщения
        if callback.message.audio:
            try:
                await callback.message.delete()
            except:
                pass
            await callback.message.answer(text, reply_markup=keyboard)
        else:
            await callback.message.edit_text(text, reply_markup=keyboard)

        await callback.answer()
        return

    # Получаем вопросы для этого урока
    questions = await get_questions_by_lesson(test.id, lesson_id)

    if not questions:
        text = "🎓 <b>Тест</b>\n\n❌ Для этого урока пока нет вопросов."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Назад к уроку", callback_data=f"lesson_{lesson_id}")
        ]])

        # ПАТТЕРН ОДНОГО ОКНА: проверяем тип сообщения
        if callback.message.audio:
            try:
                await callback.message.delete()
            except:
                pass
            await callback.message.answer(text, reply_markup=keyboard)
        else:
            await callback.message.edit_text(text, reply_markup=keyboard)

        await callback.answer()
        return

    # Получаем лучшую попытку пользователя
    user_id = callback.from_user.id
    best_attempt = await get_best_attempt(user_id, test.id)

    # Формируем информацию о тесте
    text = f"🎓 <b>{test.title}</b>\n\n"
    text += f"🎧 Урок: {lesson.title}\n"
    text += f"❓ Вопросов: {len(questions)}\n"
    text += f"⏱️ Время: {len(questions) * test.time_per_question_seconds} сек\n"
    text += f"✅ Для прохождения: {test.passing_score}%\n\n"

    if best_attempt:
        percentage = int(best_attempt.score / best_attempt.max_score * 100) if best_attempt.max_score > 0 else 0
        status = "✅ Пройден" if best_attempt.passed else "❌ Не пройден"
        text += f"🏆 <b>Ваш лучший результат:</b>\n"
        text += f"{status} • {best_attempt.score}/{best_attempt.max_score} ({percentage}%)\n\n"

    text += "Готовы начать тест?"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🎯 Начать тест",
        callback_data=f"start_test_{test.id}_{lesson_id}"
    ))
    if best_attempt:
        builder.add(InlineKeyboardButton(
            text="📊 История попыток",
            callback_data=f"test_history_{test.id}_{lesson_id}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад к уроку", callback_data=f"lesson_{lesson_id}"))
    builder.adjust(1)

    # ПАТТЕРН ОДНОГО ОКНА: проверяем тип сообщения
    if callback.message.audio:
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(text, reply_markup=builder.as_markup())
    else:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())

    await callback.answer()


# ==================== НАЧАЛО ПРОХОЖДЕНИЯ ТЕСТА ====================

@router.callback_query(F.data.startswith("start_test_"))
@user_required_callback
async def start_test(callback: CallbackQuery, state: FSMContext):
    """Начать прохождение теста"""
    parts = callback.data.split("_")
    test_id = int(parts[2])
    lesson_id = int(parts[3])

    # Получаем тест и вопросы
    from bot.services.database_service import get_test_by_id
    test = await get_test_by_id(test_id)

    if not test or not test.is_active:
        await callback.answer("❌ Тест недоступен", show_alert=True)
        return

    questions = await get_questions_by_lesson(test_id, lesson_id)

    if not questions:
        await callback.answer("❌ Нет вопросов", show_alert=True)
        return

    # Сохраняем данные теста в state
    await state.update_data(
        test_id=test_id,
        lesson_id=lesson_id,
        questions=[q.id for q in questions],
        current_index=0,
        answers={},
        start_message_id=callback.message.message_id,
        start_chat_id=callback.message.chat.id
    )

    await state.set_state(TestStates.in_progress)

    # Показываем первый вопрос
    await show_question(callback, state, 0)


async def show_question(callback: CallbackQuery, state: FSMContext, question_index: int):
    """Показать вопрос"""
    data = await state.get_data()
    questions_ids = data['questions']

    if question_index >= len(questions_ids):
        # Все вопросы пройдены - показываем результаты
        await show_test_results(callback, state)
        return

    question_id = questions_ids[question_index]
    question = await get_question_by_id(question_id)

    if not question:
        await callback.answer("❌ Ошибка загрузки вопроса", show_alert=True)
        return

    # Формируем текст вопроса
    text = f"🎓 <b>Вопрос {question_index + 1} из {len(questions_ids)}</b>\n\n"
    text += f"❓ {question.question_text}\n\n"

    # Варианты ответа
    builder = InlineKeyboardBuilder()
    for i, option in enumerate(question.options_list):
        builder.add(InlineKeyboardButton(
            text=f"{i + 1}. {option}",
            callback_data=f"answer_{question_id}_{i}"
        ))

    builder.add(InlineKeyboardButton(text="❌ Отменить тест", callback_data=f"cancel_test_{data['lesson_id']}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ==================== ОБРАБОТКА ОТВЕТОВ ====================

@router.callback_query(F.data.startswith("answer_"))
@user_required_callback
async def process_answer(callback: CallbackQuery, state: FSMContext):
    """Обработать ответ на вопрос"""
    parts = callback.data.split("_")
    question_id = int(parts[1])
    answer_index = int(parts[2])

    data = await state.get_data()

    # Сохраняем ответ
    answers = data.get('answers', {})
    answers[str(question_id)] = answer_index
    await state.update_data(answers=answers)

    # Переходим к следующему вопросу
    current_index = data.get('current_index', 0)
    await state.update_data(current_index=current_index + 1)

    await show_question(callback, state, current_index + 1)


# ==================== ПОКАЗ РЕЗУЛЬТАТОВ ====================

async def show_test_results(callback: CallbackQuery, state: FSMContext):
    """Показать результаты теста"""
    data = await state.get_data()

    test_id = data['test_id']
    lesson_id = data['lesson_id']
    answers = data['answers']
    questions_ids = data['questions']

    # Подсчитываем результат
    score = 0
    max_score = len(questions_ids)

    for question_id in questions_ids:
        question = await get_question_by_id(question_id)
        if question and str(question_id) in answers:
            user_answer = answers[str(question_id)]
            if question.is_correct(user_answer):
                score += 1

    # Вычисляем процент
    percentage = int(score / max_score * 100) if max_score > 0 else 0

    # Получаем тест для определения прохождения
    from bot.services.database_service import get_test_by_id
    test = await get_test_by_id(test_id)
    passed = percentage >= test.passing_score

    # Сохраняем попытку
    try:
        attempt = await create_attempt(
            user_id=callback.from_user.id,
            test_id=test_id,
            score=score,
            max_score=max_score,
            passed=passed,
            answers=answers,
            time_spent_seconds=0  # TODO: добавить подсчёт времени
        )
    except Exception as e:
        logger.error(f"Ошибка сохранения попытки: {e}")

    # Формируем сообщение с результатами
    text = f"🎯 <b>Тест завершён!</b>\n\n"
    text += f"📊 <b>Ваш результат:</b>\n"
    text += f"{'✅' if passed else '❌'} {score}/{max_score} ({percentage}%)\n\n"

    if passed:
        text += f"🎉 <b>Поздравляем!</b>\n"
        text += f"Вы успешно прошли тест!\n"
        text += f"Требовалось: {test.passing_score}%"
    else:
        text += f"😔 <b>Попробуйте ещё раз!</b>\n"
        text += f"Для прохождения нужно: {test.passing_score}%\n"
        text += f"Вам не хватило: {test.passing_score - percentage}%"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🔄 Пройти ещё раз", callback_data=f"start_test_{test_id}_{lesson_id}"))
    builder.add(InlineKeyboardButton(text="📊 История попыток", callback_data=f"test_history_{test_id}_{lesson_id}"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад к уроку", callback_data=f"lesson_{lesson_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await state.clear()
    await callback.answer("✅ Результат сохранён!")


# ==================== ОТМЕНА ТЕСТА ====================

@router.callback_query(F.data.startswith("cancel_test_"))
@user_required_callback
async def cancel_test(callback: CallbackQuery, state: FSMContext):
    """Отменить прохождение теста"""
    lesson_id_str = callback.data.split("_")[2]

    # Проверяем, это тест урока или общий тест
    if lesson_id_str == "None":
        # Общий тест - возвращаемся к серии
        data = await state.get_data()
        series_id = data.get("series_id")

        if series_id:
            await callback.message.edit_text(
                "❌ <b>Тест отменён</b>\n\n"
                "Ваш прогресс не сохранён.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ Назад к серии", callback_data=f"series_{series_id}")
                ]])
            )
        else:
            # Если series_id не найден, возвращаемся в главное меню
            await callback.message.edit_text(
                "❌ <b>Тест отменён</b>\n\n"
                "Ваш прогресс не сохранён.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
                ]])
            )
    else:
        # Тест урока - возвращаемся к уроку
        lesson_id = int(lesson_id_str)

        await callback.message.edit_text(
            "❌ <b>Тест отменён</b>\n\n"
            "Ваш прогресс не сохранён.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Назад к уроку", callback_data=f"lesson_{lesson_id}")
            ]])
        )

    await state.clear()
    await callback.answer()


# ==================== ИСТОРИЯ ПОПЫТОК ====================

@router.callback_query(F.data.startswith("test_history_"))
@user_required_callback
async def show_test_history(callback: CallbackQuery):
    """Показать историю попыток"""
    parts = callback.data.split("_")
    test_id = int(parts[2])
    lesson_id = int(parts[3])

    # Получаем все попытки пользователя
    from bot.services.database_service import get_attempts_by_user
    attempts = await get_attempts_by_user(callback.from_user.id, test_id)

    # Фильтруем попытки для конкретного урока
    lesson_attempts = [a for a in attempts if a.lesson_id == lesson_id]

    if not lesson_attempts:
        await callback.message.edit_text(
            "📊 <b>История попыток</b>\n\n"
            "❌ У вас пока нет попыток по этому тесту.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🎯 Пройти тест", callback_data=f"start_test_{test_id}_{lesson_id}"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"test_after_lesson_{lesson_id}")
            ]])
        )
        await callback.answer()
        return

    # Сортируем по дате (новые первые)
    lesson_attempts.sort(key=lambda x: x.completed_at if x.completed_at else x.created_at, reverse=True)

    # Находим лучшую попытку
    best = max(lesson_attempts, key=lambda x: x.score)

    text = f"📊 <b>История попыток</b>\n\n"
    text += f"Всего попыток: {len(lesson_attempts)}\n\n"

    # Показываем последние 5 попыток
    for i, attempt in enumerate(lesson_attempts[:5], 1):
        percentage = int(attempt.score / attempt.max_score * 100) if attempt.max_score > 0 else 0
        status = "✅" if attempt.passed else "❌"
        is_best = " 🏆" if attempt.id == best.id else ""

        text += f"{i}. {status} {attempt.score}/{attempt.max_score} ({percentage}%){is_best}\n"
        if attempt.completed_at:
            text += f"   {attempt.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

    text += f"\n🏆 <b>Лучший результат:</b> {best.score}/{best.max_score} ({int(best.score / best.max_score * 100)}%)"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🔄 Пройти ещё раз", callback_data=f"start_test_{test_id}_{lesson_id}"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"test_after_lesson_{lesson_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ==================== ТЕСТЫ ПО УРОКАМ (новая навигация) ====================

@router.callback_query(F.data.startswith("lesson_test_"))
@user_required_callback
async def start_lesson_test_new(callback: CallbackQuery, state: FSMContext):
    """Начать тест по конкретному уроку (новая навигация)"""
    lesson_id = int(callback.data.split("_")[2])

    # Используем существующую функцию
    # CallbackQuery frozen - используем copy() и object.__setattr__()
    from copy import copy
    new_callback = copy(callback)
    object.__setattr__(new_callback, 'data', f"test_after_lesson_{lesson_id}")
    await show_test_after_lesson(new_callback, state)


# ==================== ОБЩИЙ ТЕСТ ПО СЕРИИ ====================

@router.callback_query(F.data.startswith("general_test_"))
@user_required_callback
async def show_general_test(callback: CallbackQuery, state: FSMContext):
    """Показать общий тест по всей серии"""
    series_id = int(callback.data.split("_")[2])

    # Получаем серию
    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("📁 Серия не найдена", show_alert=True)
        return

    # Получаем тест серии
    test = await get_test_by_series(series_id)

    if not test or not test.is_active:
        await callback.message.edit_text(
            "🎓 <b>Общий тест</b>\n\n"
            "❌ Для этой серии пока нет теста.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Назад к серии", callback_data=f"series_{series_id}")
            ]])
        )
        await callback.answer()
        return

    # Получаем все вопросы теста
    all_questions = await get_questions_by_test(test.id)

    if not all_questions:
        await callback.message.edit_text(
            "🎓 <b>Общий тест</b>\n\n"
            "❌ В этом тесте пока нет вопросов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Назад к серии", callback_data=f"series_{series_id}")
            ]])
        )
        await callback.answer()
        return

    # Получаем лучшую попытку пользователя (без привязки к уроку)
    user_id = callback.from_user.id
    best_attempt = await get_best_attempt(user_id, test.id)

    # Формируем информацию о тесте
    text = f"🎓 <b>{test.title}</b>\n\n"
    text += f"📁 Серия: {series.display_name}\n"
    text += f"❓ Всего вопросов: {len(all_questions)}\n"
    text += f"⏱️ Время: {len(all_questions) * test.time_per_question_seconds} сек\n"
    text += f"✅ Для прохождения: {test.passing_score}%\n\n"

    if best_attempt:
        percentage = int(best_attempt.score / best_attempt.max_score * 100) if best_attempt.max_score > 0 else 0
        status = "✅ Пройден" if best_attempt.passed else "❌ Не пройден"
        text += f"🏆 <b>Ваш лучший результат:</b>\n"
        text += f"{status} • {best_attempt.score}/{best_attempt.max_score} ({percentage}%)\n\n"

    text += "Готовы начать общий тест по всей серии?"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🎯 Начать тест",
        callback_data=f"start_general_test_{test.id}_{series_id}"
    ))
    if best_attempt:
        builder.add(InlineKeyboardButton(
            text="📊 История попыток",
            callback_data=f"general_test_history_{test.id}_{series_id}"
        ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад к серии", callback_data=f"series_{series_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("start_general_test_"))
@user_required_callback
async def start_general_test(callback: CallbackQuery, state: FSMContext):
    """Начать прохождение общего теста по серии"""
    parts = callback.data.split("_")
    test_id = int(parts[3])
    series_id = int(parts[4])

    # Получаем тест и все вопросы
    from bot.services.database_service import get_test_by_id
    test = await get_test_by_id(test_id)

    if not test or not test.is_active:
        await callback.answer("❌ Тест недоступен", show_alert=True)
        return

    all_questions = await get_questions_by_test(test_id)

    if not all_questions:
        await callback.answer("❌ Нет вопросов", show_alert=True)
        return

    # Сохраняем данные теста в state (без lesson_id для общего теста)
    await state.update_data(
        test_id=test_id,
        series_id=series_id,
        lesson_id=None,  # Общий тест не привязан к конкретному уроку
        questions=[q.id for q in all_questions],
        current_index=0,
        answers={},
        start_message_id=callback.message.message_id,
        start_chat_id=callback.message.chat.id
    )

    await state.set_state(TestStates.in_progress)

    # Показываем первый вопрос
    await show_question(callback, state, 0)


@router.callback_query(F.data.startswith("general_test_history_"))
@user_required_callback
async def show_general_test_history(callback: CallbackQuery):
    """Показать историю попыток общего теста"""
    parts = callback.data.split("_")
    test_id = int(parts[3])
    series_id = int(parts[4])

    # Получаем все попытки пользователя
    from bot.services.database_service import get_attempts_by_user
    attempts = await get_attempts_by_user(callback.from_user.id, test_id)

    # Фильтруем попытки общего теста (без привязки к уроку)
    general_attempts = [a for a in attempts if a.lesson_id is None]

    if not general_attempts:
        await callback.message.edit_text(
            "📊 <b>История попыток</b>\n\n"
            "❌ У вас пока нет попыток по этому тесту.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🎯 Пройти тест", callback_data=f"start_general_test_{test_id}_{series_id}"),
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"general_test_{series_id}")
            ]])
        )
        await callback.answer()
        return

    # Сортируем по дате (новые первые)
    general_attempts.sort(key=lambda x: x.completed_at if x.completed_at else x.created_at, reverse=True)

    # Находим лучшую попытку
    best = max(general_attempts, key=lambda x: x.score)

    text = f"📊 <b>История попыток</b>\n\n"
    text += f"Всего попыток: {len(general_attempts)}\n\n"

    # Показываем последние 5 попыток
    for i, attempt in enumerate(general_attempts[:5], 1):
        percentage = int(attempt.score / attempt.max_score * 100) if attempt.max_score > 0 else 0
        status = "✅" if attempt.passed else "❌"
        is_best = " 🏆" if attempt.id == best.id else ""

        text += f"{i}. {status} {attempt.score}/{attempt.max_score} ({percentage}%){is_best}\n"
        if attempt.completed_at:
            text += f"   {attempt.completed_at.strftime('%d.%m.%Y %H:%M')}\n"

    text += f"\n🏆 <b>Лучший результат:</b> {best.score}/{best.max_score} ({int(best.score / best.max_score * 100)}%)"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🔄 Пройти ещё раз", callback_data=f"start_general_test_{test_id}_{series_id}"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data=f"general_test_{series_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
