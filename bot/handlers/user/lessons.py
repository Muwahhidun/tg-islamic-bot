from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.services.database_service import LessonService, BookService
from bot.keyboards.user import get_lessons_keyboard, get_lesson_control_keyboard
from bot.utils.decorators import user_required_callback
from bot.utils.audio_utils import AudioUtils


router = Router()


@router.callback_query(F.data.startswith("book_"))
@user_required_callback
async def show_lessons(callback: CallbackQuery):
    """
    Показать уроки выбранной книги
    """
    book_id = int(callback.data.split("_")[1])
    book = await BookService.get_book_by_id(book_id)

    if not book:
        await callback.answer("Книга не найдена", show_alert=True)
        return

    lessons = await LessonService.get_lessons_by_book(book_id)

    if not lessons:
        await callback.answer("В этой книге пока нет уроков", show_alert=True)
        return

    text = (
        f"📖 Книга: «{book.name}»\n"
        f"✍️ Автор: {book.author_info}\n\n"
        f"Список уроков ({len(lessons)}):"
    )
    # Передаем theme_id в клавиатуру
    keyboard = get_lessons_keyboard(lessons, theme_id=book.theme_id)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("lesson_"))
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
        await callback.answer(f"Ошибка при загрузке аудио: {e}", show_alert=True)
        return

    await callback.answer()


@router.callback_query(F.data.startswith("prev_"))
@user_required_callback
async def previous_lesson(callback: CallbackQuery):
    """
    Перейти к предыдущему уроку
    """
    current_lesson_id = int(callback.data.split("_")[1])
    current_lesson = await LessonService.get_lesson_by_id(current_lesson_id)

    if not current_lesson:
        await callback.answer("Урок не найден", show_alert=True)
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
        await callback.answer("Это первый урок в книге", show_alert=True)
        return

    # Переход к предыдущему уроку
    prev_lesson = lessons[current_index - 1]

    # Формирование callback_data для предыдущего урока
    callback.data = f"lesson_{prev_lesson.id}"
    await play_lesson(callback)


@router.callback_query(F.data.startswith("next_"))
@user_required_callback
async def next_lesson(callback: CallbackQuery):
    """
    Перейти к следующему уроку
    """
    current_lesson_id = int(callback.data.split("_")[1])
    current_lesson = await LessonService.get_lesson_by_id(current_lesson_id)

    if not current_lesson:
        await callback.answer("Урок не найден", show_alert=True)
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
        await callback.answer("Это последний урок в книге", show_alert=True)
        return

    # Переход к следующему уроку
    next_lesson = lessons[current_index + 1]

    # Формирование callback_data для следующего урока
    callback.data = f"lesson_{next_lesson.id}"
    await play_lesson(callback)


@router.callback_query(F.data.startswith("back_to_book_"))
@user_required_callback
async def back_to_book(callback: CallbackQuery):
    """
    Вернуться к книге
    """
    book_id = int(callback.data.split("_")[3])
    callback.data = f"book_{book_id}"
    await show_lessons(callback)


