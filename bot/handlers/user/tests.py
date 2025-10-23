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


async def get_back_to_lesson_callback(lesson_id: int, state: FSMContext) -> str:
    """
    Формирует правильный callback для возврата к уроку с учётом контекста навигации.

    Args:
        lesson_id: ID урока
        state: FSM context для проверки teacher_id

    Returns:
        str: Callback data для кнопки возврата к уроку
    """
    data = await state.get_data()
    teacher_id = data.get("teacher_id")

    if teacher_id:
        return f"teacher_{teacher_id}_play_lesson_{lesson_id}"
    else:
        return f"lesson_{lesson_id}"


async def get_back_to_series_callback(series_id: int, state: FSMContext) -> str:
    """
    Формирует правильный callback для возврата к серии с учётом контекста навигации.

    Args:
        series_id: ID серии
        state: FSM context для проверки teacher_id

    Returns:
        str: Callback data для кнопки возврата к серии
    """
    data = await state.get_data()
    teacher_id = data.get("teacher_id")

    if teacher_id:
        return f"teacher_{teacher_id}_series_{series_id}"
    else:
        return f"series_{series_id}"


# ==================== ПОКАЗ ДОСТУПНЫХ ТЕСТОВ ====================

@router.callback_query(F.data.startswith("test_after_lesson_"))
@user_required_callback
async def show_test_after_lesson(callback: CallbackQuery, state: FSMContext, user):
    """Показать тест после прослушивания урока"""
    parts = callback.data.split("_")
    lesson_id_str = parts[3]

    # Если lesson_id это "None", значит это общий тест - не обрабатываем здесь
    if lesson_id_str == "None":
        await callback.answer("❌ Ошибка навигации", show_alert=True)
        return

    lesson_id = int(lesson_id_str)

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
        back_callback = await get_back_to_lesson_callback(lesson_id, state)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Назад к уроку", callback_data=back_callback)
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
        back_callback = await get_back_to_lesson_callback(lesson_id, state)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Назад к уроку", callback_data=back_callback)
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

    # Получаем лучшую попытку пользователя для этого урока (используем database user_id)
    best_attempt = await get_best_attempt(user.id, test.id, lesson_id)

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
    builder.add(InlineKeyboardButton(
        text="📊 История попыток",
        callback_data=f"test_history_{test.id}_{lesson_id}"
    ))
    back_callback = await get_back_to_lesson_callback(lesson_id, state)
    builder.add(InlineKeyboardButton(text="⬅️ Назад к уроку", callback_data=back_callback))
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
    lesson_id = int(parts[3]) if parts[3] != "None" else None

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
    from bot.services.database_service import get_test_by_id, get_user_by_telegram_id
    test = await get_test_by_id(test_id)
    passed = percentage >= test.passing_score

    # Получаем database user_id по telegram_id
    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        await state.clear()
        return

    # Сохраняем попытку
    try:
        attempt = await create_attempt(
            user_id=user.id,  # database user_id, а не telegram_id
            test_id=test_id,
            score=score,
            max_score=max_score,
            passed=passed,
            answers=answers,
            time_spent_seconds=0,  # TODO: добавить подсчёт времени
            lesson_id=lesson_id  # None для общего теста, иначе ID урока
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

    # Проверяем контекст навигации через преподавателя
    data = await state.get_data()
    teacher_id = data.get("teacher_id")

    builder = InlineKeyboardBuilder()

    # Проверяем тип теста: урок или общий
    if lesson_id is None:
        # ОБЩИЙ ТЕСТ (по всей серии)
        # Получаем series_id для возврата
        series_id = test.series_id if test else None

        if teacher_id and series_id:
            # Через преподавателей
            builder.add(InlineKeyboardButton(text="🔄 Пройти ещё раз", callback_data=f"teacher_{teacher_id}_general_test_{series_id}"))
            builder.add(InlineKeyboardButton(text="📊 История попыток", callback_data=f"general_test_history_{test_id}_{series_id}"))
            back_callback = await get_back_to_series_callback(series_id, state)
            builder.add(InlineKeyboardButton(text="⬅️ Назад к серии", callback_data=back_callback))
        else:
            # Через темы
            builder.add(InlineKeyboardButton(text="🔄 Пройти ещё раз", callback_data=f"start_general_test_{test_id}_{series_id}"))
            builder.add(InlineKeyboardButton(text="📊 История попыток", callback_data=f"general_test_history_{test_id}_{series_id}"))
            if series_id:
                builder.add(InlineKeyboardButton(text="⬅️ Назад к серии", callback_data=f"series_{series_id}"))
            else:
                builder.add(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    else:
        # ТЕСТ УРОКА
        back_callback = await get_back_to_lesson_callback(lesson_id, state)

        if teacher_id:
            # Через преподавателей
            builder.add(InlineKeyboardButton(text="🔄 Пройти ещё раз", callback_data=f"teacher_{teacher_id}_start_test_{test_id}_{lesson_id}"))
            builder.add(InlineKeyboardButton(text="📊 История попыток", callback_data=f"test_history_{test_id}_{lesson_id}"))
        else:
            # Через темы
            builder.add(InlineKeyboardButton(text="🔄 Пройти ещё раз", callback_data=f"start_test_{test_id}_{lesson_id}"))
            builder.add(InlineKeyboardButton(text="📊 История попыток", callback_data=f"test_history_{test_id}_{lesson_id}"))

        builder.add(InlineKeyboardButton(text="⬅️ Назад к уроку", callback_data=back_callback))

    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())

    # Очищаем состояние, но сохраняем teacher_id если он есть
    if teacher_id:
        await state.clear()
        await state.update_data(teacher_id=teacher_id)
    else:
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
            back_callback = await get_back_to_series_callback(series_id, state)
            await callback.message.edit_text(
                "❌ <b>Тест отменён</b>\n\n"
                "Ваш прогресс не сохранён.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="⬅️ Назад к серии", callback_data=back_callback)
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

        back_callback = await get_back_to_lesson_callback(lesson_id, state)

        await callback.message.edit_text(
            "❌ <b>Тест отменён</b>\n\n"
            "Ваш прогресс не сохранён.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Назад к уроку", callback_data=back_callback)
            ]])
        )

    await state.clear()
    await callback.answer()


# ==================== ИСТОРИЯ ПОПЫТОК ====================

@router.callback_query(F.data.startswith("test_history_"))
@user_required_callback
async def show_test_history(callback: CallbackQuery, state: FSMContext, user):
    """Показать историю попыток"""
    parts = callback.data.split("_")
    test_id = int(parts[2])
    lesson_id = int(parts[3]) if parts[3] != "None" else None

    # Получаем все попытки пользователя (используем database user_id)
    from bot.services.database_service import get_attempts_by_user
    attempts = await get_attempts_by_user(user.id, test_id)

    # Фильтруем попытки для конкретного урока
    lesson_attempts = [a for a in attempts if a.lesson_id == lesson_id]

    # Определяем правильный callback для возврата
    if lesson_id:
        back_callback = await get_back_to_lesson_callback(lesson_id, state)
    else:
        # Для общих тестов нужно вернуться к списку общих тестов
        # Получаем series_id из теста
        from bot.services.database_service import get_test_by_id
        test = await get_test_by_id(test_id)
        if test and test.series_id:
            back_callback = await get_back_to_series_callback(test.series_id, state)
        else:
            back_callback = "menu"

    if not lesson_attempts:
        await callback.message.edit_text(
            "📊 <b>История попыток</b>\n\n"
            "❌ У вас пока нет попыток по этому тесту.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🎯 Пройти тест", callback_data=f"start_test_{test_id}_{lesson_id if lesson_id else 'None'}"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)
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
    builder.add(InlineKeyboardButton(text="🔄 Пройти ещё раз", callback_data=f"start_test_{test_id}_{lesson_id if lesson_id else 'None'}"))
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback))
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

@router.callback_query(F.data.startswith("general_test_") & ~F.data.startswith("general_test_history_"))
@user_required_callback
async def show_general_test(callback: CallbackQuery, state: FSMContext, user):
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
        back_callback = await get_back_to_series_callback(series_id, state)
        await callback.message.edit_text(
            "🎓 <b>Общий тест</b>\n\n"
            "❌ Для этой серии пока нет теста.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Назад к серии", callback_data=back_callback)
            ]])
        )
        await callback.answer()
        return

    # Получаем все вопросы теста
    all_questions = await get_questions_by_test(test.id)

    if not all_questions:
        back_callback = await get_back_to_series_callback(series_id, state)
        await callback.message.edit_text(
            "🎓 <b>Общий тест</b>\n\n"
            "❌ В этом тесте пока нет вопросов.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="⬅️ Назад к серии", callback_data=back_callback)
            ]])
        )
        await callback.answer()
        return

    # Получаем лучшую попытку пользователя для общего теста (lesson_id=None)
    best_attempt = await get_best_attempt(user.id, test.id, lesson_id=None)

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

    back_callback = await get_back_to_series_callback(series_id, state)

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🎯 Начать тест",
        callback_data=f"start_general_test_{test.id}_{series_id}"
    ))
    builder.add(InlineKeyboardButton(
        text="📊 История попыток",
        callback_data=f"general_test_history_{test.id}_{series_id}"
    ))
    builder.add(InlineKeyboardButton(text="⬅️ Назад к серии", callback_data=back_callback))
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
async def show_general_test_history(callback: CallbackQuery, user):
    """Показать историю попыток общего теста"""
    parts = callback.data.split("_")
    test_id = int(parts[3])
    series_id = int(parts[4])

    # Получаем все попытки пользователя (используем database user_id)
    from bot.services.database_service import get_attempts_by_user
    attempts = await get_attempts_by_user(user.id, test_id)

    # Фильтруем попытки общего теста (без привязки к уроку)
    general_attempts = [a for a in attempts if a.lesson_id is None]

    if not general_attempts:
        await callback.message.edit_text(
            "📊 <b>История попыток</b>\n\n"
            "❌ У вас пока нет попыток по этому тесту.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🎯 Пройти тест", callback_data=f"start_general_test_{test_id}_{series_id}"),
                InlineKeyboardButton(text="⬅️ Назад", callback_data=f"general_test_{series_id}")
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
    builder.add(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"general_test_{series_id}"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
