from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from bot.services.database_service import LessonService, get_test_by_series, get_questions_by_lesson
from bot.keyboards.user import get_lesson_control_keyboard
from bot.utils.decorators import user_required_callback
from bot.utils.audio_utils import AudioUtils


router = Router()


@router.callback_query(F.data.startswith("lesson_") & ~F.data.startswith("lesson_test_"))
@user_required_callback
async def play_lesson(callback: CallbackQuery):
    """
    Воспроизведение урока
    """
    lesson_id = int(callback.data.split("_")[1])
    lesson = await LessonService.get_lesson_by_id(lesson_id)

    if not lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    if not lesson.has_audio():
        await callback.answer("Аудиофайл недоступен", show_alert=True)
        return

    # Проверка существования файла
    if not AudioUtils.file_exists(lesson.audio_path):
        await callback.answer("Аудиофайл не найден", show_alert=True)
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

    # Проверяем, есть ли тест для этого конкретного урока
    has_test = False
    if lesson.series_id:
        test = await get_test_by_series(lesson.series_id)
        if test and test.is_active:
            # Проверяем, есть ли вопросы для этого урока
            questions = await get_questions_by_lesson(test.id, lesson.id)
            has_test = len(questions) > 0

    # Клавиатура управления
    keyboard = get_lesson_control_keyboard(lesson, has_test=has_test)

    # ПАТТЕРН ОДНОГО ОКНА: удаляем предыдущее сообщение
    try:
        await callback.message.delete()
    except:
        pass

    try:
        # Если есть кешированный file_id - используем его (быстро!)
        if lesson.telegram_file_id:
            sent_message = await callback.message.answer_audio(
                audio=lesson.telegram_file_id,
                caption=caption,
                reply_markup=keyboard
            )
        else:
            # Первая отправка - загружаем файл и сохраняем file_id
            audio_file = FSInputFile(lesson.audio_path)
            sent_message = await callback.message.answer_audio(
                audio=audio_file,
                title=lesson.title,
                caption=caption,
                reply_markup=keyboard
            )

            # Сохраняем file_id для следующих отправок
            if sent_message.audio:
                lesson.telegram_file_id = sent_message.audio.file_id
                # Обновляем в БД
                from bot.services.database_service import update_lesson
                await update_lesson(lesson)

    except Exception as e:
        # Ограничиваем длину сообщения для alert (макс 200 символов)
        error_msg = str(e)[:150]
        await callback.answer(f"❌ Ошибка загрузки аудио", show_alert=True)
        return

    await callback.answer()


@router.callback_query(F.data.startswith("prev_"))
@user_required_callback
async def previous_lesson(callback: CallbackQuery):
    """
    Перейти к предыдущему уроку в серии
    """
    current_lesson_id = int(callback.data.split("_")[1])
    current_lesson = await LessonService.get_lesson_by_id(current_lesson_id)

    if not current_lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    if not current_lesson.series_id:
        await callback.answer("Урок не принадлежит серии", show_alert=True)
        return

    # Получение всех уроков серии
    lessons = await LessonService.get_lessons_by_series(current_lesson.series_id)

    # Поиск текущего урока в списке
    current_index = None
    for i, lesson in enumerate(lessons):
        if lesson.id == current_lesson_id:
            current_index = i
            break

    if current_index is None or current_index == 0:
        await callback.answer("Это первый урок в серии", show_alert=True)
        return

    # Переход к предыдущему уроку
    prev_lesson = lessons[current_index - 1]

    # Имитируем вызов с новым lesson_id
    # Создаем новый callback с измененным data
    from aiogram.types import CallbackQuery as CQ
    from copy import copy
    new_callback = copy(callback)
    object.__setattr__(new_callback, 'data', f"lesson_{prev_lesson.id}")
    await play_lesson(new_callback)


@router.callback_query(F.data.startswith("next_"))
@user_required_callback
async def next_lesson(callback: CallbackQuery):
    """
    Перейти к следующему уроку в серии
    """
    current_lesson_id = int(callback.data.split("_")[1])
    current_lesson = await LessonService.get_lesson_by_id(current_lesson_id)

    if not current_lesson:
        await callback.answer("Урок не найден", show_alert=True)
        return

    if not current_lesson.series_id:
        await callback.answer("Урок не принадлежит серии", show_alert=True)
        return

    # Получение всех уроков серии
    lessons = await LessonService.get_lessons_by_series(current_lesson.series_id)

    # Поиск текущего урока в списке
    current_index = None
    for i, lesson in enumerate(lessons):
        if lesson.id == current_lesson_id:
            current_index = i
            break

    if current_index is None or current_index == len(lessons) - 1:
        await callback.answer("Это последний урок в серии", show_alert=True)
        return

    # Переход к следующему уроку
    next_lesson = lessons[current_index + 1]

    # Имитируем вызов с новым lesson_id
    # Создаем новый callback с измененным data
    from copy import copy
    new_callback = copy(callback)
    object.__setattr__(new_callback, 'data', f"lesson_{next_lesson.id}")
    await play_lesson(new_callback)


@router.callback_query(F.data.startswith("author_"))
@user_required_callback
async def show_author_info(callback: CallbackQuery):
    """
    Показать информацию об авторе книги
    """
    author_id = int(callback.data.split("_")[1])

    from bot.services.database_service import get_book_author_by_id
    author = await get_book_author_by_id(author_id)

    if not author:
        await callback.answer("❌ Автор не найден", show_alert=True)
        return

    # Формируем информацию об авторе
    info = f"✍️ <b>{author.name}</b>\n\n"

    if author.biography:
        info += f"{author.biography}\n\n"

    if author.birth_year:
        info += f"📅 Год рождения: {author.birth_year}\n"

    if author.death_year:
        info += f"⚰️ Год смерти: {author.death_year}\n"

    # Кнопка "Закрыть"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Закрыть", callback_data="close_info")]
    ])

    await callback.message.answer(info, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("teacher_"))
@user_required_callback
async def show_teacher_info(callback: CallbackQuery):
    """
    Показать информацию о преподавателе
    """
    teacher_id = int(callback.data.split("_")[1])

    from bot.services.database_service import get_lesson_teacher_by_id
    teacher = await get_lesson_teacher_by_id(teacher_id)

    if not teacher:
        await callback.answer("❌ Преподаватель не найден", show_alert=True)
        return

    # Формируем информацию о преподавателе
    info = f"🎙️ <b>{teacher.name}</b>\n\n"

    if teacher.biography:
        info += f"{teacher.biography}\n\n"

    # Кнопка "Закрыть"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Закрыть", callback_data="close_info")]
    ])

    await callback.message.answer(info, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("book_info_"))
@user_required_callback
async def show_book_info(callback: CallbackQuery):
    """
    Показать информацию о книге
    """
    book_id = int(callback.data.split("_")[2])

    from bot.services.database_service import get_book_by_id
    book = await get_book_by_id(book_id)

    if not book:
        await callback.answer("❌ Книга не найдена", show_alert=True)
        return

    # Формируем информацию о книге
    info = f"📖 <b>{book.name}</b>\n\n"

    if book.author:
        info += f"✍️ Автор: {book.author.name}\n"

    if book.theme:
        info += f"📚 Тема: {book.theme.name}\n"

    if book.desc:
        info += f"\n{book.desc}\n"

    # Кнопка "Закрыть"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Закрыть", callback_data="close_info")]
    ])

    await callback.message.answer(info, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "close_info")
@user_required_callback
async def close_info(callback: CallbackQuery):
    """
    Закрыть информационное сообщение
    """
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer()


