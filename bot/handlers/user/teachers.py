"""
Обработчики для навигации по преподавателям (пользовательский интерфейс)
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.services.database_service import (
    LessonTeacherService,
    get_themes_by_teacher,
    get_books_by_teacher_and_theme,
    get_series_by_teacher_and_book,
    BookService,
    get_series_by_id,
    get_test_by_series,
    LessonService,
    get_questions_by_lesson,
    get_bookmark_by_user_and_lesson,
    get_user_by_telegram_id,
    update_lesson,
    count_user_bookmarks,
    get_lesson_by_id,
    create_bookmark,
    get_bookmark_by_id,
    update_bookmark_name,
    delete_bookmark,
)
from bot.keyboards.user import (
    get_teachers_keyboard,
    get_teacher_themes_keyboard,
    get_teacher_books_keyboard,
    get_teacher_series_keyboard,
    get_teacher_series_menu_keyboard,
    get_teacher_lessons_keyboard,
    get_teacher_lesson_control_keyboard,
)
from bot.utils.decorators import user_required_callback
from bot.utils.audio_utils import AudioUtils
from bot.states.bookmark_states import BookmarkStates
from bot.handlers.user.bookmarks import MAX_BOOKMARKS

router = Router()


async def safe_edit_or_send(callback: CallbackQuery, text: str, reply_markup=None):
    """
    Безопасно редактирует текст сообщения или отправляет новое, если редактирование невозможно
    (например, при попытке отредактировать аудио-сообщение)
    """
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        # Не удалось отредактировать (возможно, это аудио/медиа-сообщение)
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(text, reply_markup=reply_markup)


@router.callback_query(F.data == "show_teachers")
@user_required_callback
async def show_teachers_handler(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки 'Список преподавателей' - показывает список доступных преподавателей
    """
    # Очищаем состояние
    await state.clear()

    teachers = await LessonTeacherService.get_all_active_teachers()

    text = "👤 Выберите преподавателя:"
    keyboard = get_teachers_keyboard(teachers)

    if not teachers:
        text = "📭 Пока нет доступных преподавателей"

    await safe_edit_or_send(callback, text, reply_markup=keyboard if teachers else None)
    await callback.answer()


@router.callback_query(F.data.startswith("teacher_nav_"))
@user_required_callback
async def show_teacher_themes(callback: CallbackQuery, state: FSMContext):
    """
    Показать список тем выбранного преподавателя
    """
    # Очищаем состояние
    await state.clear()

    teacher_id = int(callback.data.split("_")[2])
    teacher = await LessonTeacherService.get_teacher_by_id(teacher_id)

    if not teacher:
        await callback.answer("❌ Преподаватель не найден", show_alert=True)
        return

    themes = await get_themes_by_teacher(teacher_id)

    if not themes:
        await callback.answer("📭 У этого преподавателя пока нет доступных тем", show_alert=True)
        return

    text = f"🎙️ Преподаватель: {teacher.name}\n\nВыберите тему:"
    keyboard = get_teacher_themes_keyboard(themes, teacher_id)

    await safe_edit_or_send(callback, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_theme_\d+$"))
@user_required_callback
async def show_teacher_books(callback: CallbackQuery, state: FSMContext):
    """
    Показать книги преподавателя по выбранной теме
    """
    # Очищаем состояние
    await state.clear()

    parts = callback.data.split("_")
    teacher_id = int(parts[1])
    theme_id = int(parts[3])

    teacher = await LessonTeacherService.get_teacher_by_id(teacher_id)
    if not teacher:
        await callback.answer("❌ Преподаватель не найден", show_alert=True)
        return

    books = await get_books_by_teacher_and_theme(teacher_id, theme_id)

    if not books:
        await callback.answer("📭 У этого преподавателя нет книг по данной теме", show_alert=True)
        return

    # Формируем текст с темой
    theme_name = books[0].theme.name if books and books[0].theme else "Неизвестная тема"
    text = (
        f"🎙️ Преподаватель: {teacher.name}\n"
        f"📚 Тема: {theme_name}\n\n"
        f"Выберите книгу:"
    )
    keyboard = get_teacher_books_keyboard(books, teacher_id, theme_id)

    await safe_edit_or_send(callback, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_book_\d+$"))
@user_required_callback
async def show_teacher_series(callback: CallbackQuery, state: FSMContext):
    """
    Показать серии преподавателя по выбранной книге
    """
    # Очищаем состояние
    await state.clear()

    parts = callback.data.split("_")
    teacher_id = int(parts[1])
    book_id = int(parts[3])

    teacher = await LessonTeacherService.get_teacher_by_id(teacher_id)
    book = await BookService.get_book_by_id(book_id)

    if not teacher or not book:
        await callback.answer("❌ Данные не найдены", show_alert=True)
        return

    series_list = await get_series_by_teacher_and_book(teacher_id, book_id)

    if not series_list:
        await callback.answer("📭 У этого преподавателя нет серий по данной книге", show_alert=True)
        return

    text = (
        f"🎙️ Преподаватель: {teacher.name}\n"
        f"📚 Тема: {book.theme.name if book.theme else 'Без темы'}\n"
        f"📖 Книга: «{book.name}»\n"
        f"✍️ Автор книги: {book.author_info}\n\n"
        f"Выберите серию:"
    )
    keyboard = get_teacher_series_keyboard(series_list, teacher_id, book_id)

    await safe_edit_or_send(callback, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_series_\d+$"))
@user_required_callback
async def show_teacher_series_menu(callback: CallbackQuery, state: FSMContext):
    """
    Показать меню серии для навигации через преподавателей (Уроки / Тест / Назад)
    """
    # Очищаем состояние
    await state.clear()

    parts = callback.data.split("_")
    teacher_id = int(parts[1])
    series_id = int(parts[3])

    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("❌ Серия не найдена", show_alert=True)
        return

    # Проверяем наличие теста для серии
    test = await get_test_by_series(series_id)
    has_test = test is not None

    text = (
        f"📁 <b>{series.year} - {series.name}</b>\n\n"
        f"🎙️ Преподаватель: {series.teacher.name if series.teacher else '???'}\n"
        f"📖 Книга: «{series.book.name}» ({series.book.author_info})\n"
        f"🎧 Уроков: {series.active_lessons_count}\n\n"
        f"Выберите действие:"
    )

    # Получаем book_id для навигации назад
    book_id = series.book_id if series.book_id else 0
    keyboard = get_teacher_series_menu_keyboard(series_id, teacher_id, book_id, has_test)

    await safe_edit_or_send(callback, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_series_lessons_\d+$"))
@user_required_callback
async def show_teacher_series_lessons(callback: CallbackQuery, state: FSMContext):
    """
    Показать список уроков серии для навигации через преподавателей
    """
    # Очищаем состояние
    await state.clear()

    parts = callback.data.split("_")
    teacher_id = int(parts[1])
    series_id = int(parts[4])  # teacher_X_series_lessons_Y -> parts[4] = Y

    series = await get_series_by_id(series_id)

    if not series:
        await callback.answer("❌ Серия не найдена", show_alert=True)
        return

    lessons = await LessonService.get_lessons_by_series(series_id)

    if not lessons:
        await callback.answer("📭 В этой серии пока нет уроков", show_alert=True)
        return

    # TODO: Проверить, есть ли тесты для каждого урока
    # Пока передаем пустой словарь, позже добавим проверку
    has_tests = {}

    text = (
        f"📁 <b>{series.year} - {series.name}</b>\n\n"
        f"🎙️ Преподаватель: {series.teacher.name if series.teacher else '???'}\n"
        f"📖 Книга: «{series.book.name}»\n\n"
        f"🎧 Список уроков ({len(lessons)}):"
    )

    # Получаем book_id для навигации назад
    book_id = series.book_id if series.book_id else 0
    keyboard = get_teacher_lessons_keyboard(lessons, series_id, teacher_id, book_id, has_tests)

    await safe_edit_or_send(callback, text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "back_to_teachers")
@user_required_callback
async def back_to_teachers_handler(callback: CallbackQuery, state: FSMContext):
    """
    Возврат к списку преподавателей
    """
    # Очищаем состояние
    await state.clear()

    teachers = await LessonTeacherService.get_all_active_teachers()

    text = "👤 Выберите преподавателя:"
    keyboard = get_teachers_keyboard(teachers)

    if not teachers:
        text = "📭 Пока нет доступных преподавателей"

    await safe_edit_or_send(callback, text, reply_markup=keyboard if teachers else None)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_play_lesson_\d+$"))
@user_required_callback
async def play_teacher_lesson(callback: CallbackQuery):
    """
    Воспроизведение урока из навигации через преподавателей
    """
    parts = callback.data.split("_")
    teacher_id = int(parts[1])  # teacher_X_play_lesson_Y
    lesson_id = int(parts[4])   # teacher_X_play_lesson_Y

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
        f"🎧 Урок {lesson.lesson_number}\n\n"
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

    # Проверяем, есть ли закладка на этот урок
    has_bookmark = False
    user = await get_user_by_telegram_id(callback.from_user.id)
    if user:
        bookmark = await get_bookmark_by_user_and_lesson(user.id, lesson_id)
        if bookmark:
            has_bookmark = True

    # Клавиатура управления (с контекстом преподавателя!)
    keyboard = get_teacher_lesson_control_keyboard(
        lesson,
        teacher_id=teacher_id,
        has_test=has_test,
        has_bookmark=has_bookmark
    )

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
                await update_lesson(lesson)

    except Exception as e:
        # Ограничиваем длину сообщения для alert (макс 200 символов)
        error_msg = str(e)[:150]
        await callback.answer(f"❌ Ошибка при загрузке аудио: {error_msg}", show_alert=True)
        return

    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_prev_\d+$"))
@user_required_callback
async def teacher_previous_lesson(callback: CallbackQuery):
    """
    Перейти к предыдущему уроку в серии (с контекстом преподавателя)
    """
    parts = callback.data.split("_")
    teacher_id = int(parts[1])  # teacher_X_prev_Y
    current_lesson_id = int(parts[3])  # teacher_X_prev_Y

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

    # Создаем новый callback с teacher контекстом
    from copy import copy
    new_callback = copy(callback)
    object.__setattr__(new_callback, 'data', f"teacher_{teacher_id}_play_lesson_{prev_lesson.id}")
    await play_teacher_lesson(new_callback)


@router.callback_query(F.data.regexp(r"^teacher_\d+_next_\d+$"))
@user_required_callback
async def teacher_next_lesson(callback: CallbackQuery):
    """
    Перейти к следующему уроку в серии (с контекстом преподавателя)
    """
    parts = callback.data.split("_")
    teacher_id = int(parts[1])  # teacher_X_next_Y
    current_lesson_id = int(parts[3])  # teacher_X_next_Y

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

    # Создаем новый callback с teacher контекстом
    from copy import copy
    new_callback = copy(callback)
    object.__setattr__(new_callback, 'data', f"teacher_{teacher_id}_play_lesson_{next_lesson.id}")
    await play_teacher_lesson(new_callback)


# ==================== ЗАКЛАДКИ С КОНТЕКСТОМ ПРЕПОДАВАТЕЛЯ ====================

@router.callback_query(F.data.regexp(r"^teacher_\d+_add_bookmark_\d+$"))
@user_required_callback
async def teacher_add_bookmark_start(callback: CallbackQuery, state: FSMContext):
    """Начало добавления закладки (из навигации преподавателей)"""
    parts = callback.data.split("_")
    teacher_id = int(parts[1])  # teacher_X_add_bookmark_Y
    lesson_id = int(parts[4])

    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    # Проверяем лимит закладок
    bookmarks_count = await count_user_bookmarks(user.id)
    
    if bookmarks_count >= MAX_BOOKMARKS:
        text = (
            "❌ <b>Лимит закладок</b>\n\n"
            f"У вас уже {MAX_BOOKMARKS} закладок (максимум).\n\n"
            "Удалите старые закладки, чтобы добавить новые."
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📌 Мои закладки", callback_data="bookmarks")],
            [InlineKeyboardButton(text="⬅️ К уроку", callback_data=f"teacher_{teacher_id}_play_lesson_{lesson_id}")]
        ])
        
        await callback.message.edit_caption(caption=text, reply_markup=keyboard)
        await callback.answer()
        return
    
    # Проверяем, нет ли уже закладки на этот урок
    existing_bookmark = await get_bookmark_by_user_and_lesson(user.id, lesson_id)
    if existing_bookmark:
        await callback.answer("ℹ️ Этот урок уже в закладках", show_alert=True)
        return
    
    # Получаем урок
    lesson = await get_lesson_by_id(lesson_id)
    if not lesson:
        await callback.answer("❌ Урок не найден", show_alert=True)
        return
    
    # Сохраняем данные и запрашиваем название
    await state.update_data(
        lesson_id=lesson_id,
        teacher_id=teacher_id,  # Сохраняем teacher_id для возврата
        bookmark_message_id=callback.message.message_id,
        bookmark_chat_id=callback.message.chat.id
    )
    await state.set_state(BookmarkStates.entering_name)
    
    text = (
        "📌 <b>Добавление в закладки</b>\n\n"
        f"🎧 Урок {lesson.lesson_number}\n"
    )
    
    if lesson.book and lesson.book.theme:
        text += f"📚 Тема: {lesson.book.theme.name}\n"
    if lesson.book:
        text += f"📖 Книга: «{lesson.book.name}»\n"
    
    text += "\nВведите название закладки:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"teacher_{teacher_id}_play_lesson_{lesson_id}")]
    ])
    
    await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_remove_bookmark_\d+$"))
@user_required_callback
async def teacher_remove_bookmark_from_lesson(callback: CallbackQuery, state: FSMContext):
    """Удалить закладку прямо с экрана урока (из навигации преподавателей)"""
    parts = callback.data.split("_")
    teacher_id = int(parts[1])  # teacher_X_remove_bookmark_Y
    lesson_id = int(parts[4])

    user = await get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    # Находим закладку
    bookmark = await get_bookmark_by_user_and_lesson(user.id, lesson_id)
    
    if not bookmark:
        await callback.answer("❌ Закладка не найдена", show_alert=True)
        return
    
    # Показываем меню управления закладкой
    lesson = bookmark.lesson
    
    text = f"📌 <b>Закладка: \"{bookmark.custom_name}\"</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"🎧 <b>Урок {lesson.lesson_number}</b>\n\n"
    
    if lesson.book and lesson.book.theme:
        text += f"📚 Тема: {lesson.book.theme.name}\n"
    if lesson.book:
        text += f"📖 Книга: «{lesson.book.name}»\n"
    if lesson.book and lesson.book.author:
        text += f"✍️ Автор: {lesson.book.author.name}\n"
    if lesson.teacher:
        text += f"🎙️ Преподаватель: {lesson.teacher.name}\n"
    if lesson.series:
        text += f"📁 Серия: {lesson.series.display_name}\n"
    
    text += f"\n📅 Добавлено: {bookmark.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "Выберите действие:"
    
    # Сохраняем teacher_id для других операций с закладкой
    await state.update_data(teacher_id=teacher_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"teacher_{teacher_id}_bookmark_rename_{bookmark.id}")],
        [InlineKeyboardButton(text="🗑️ Удалить закладку", callback_data=f"teacher_{teacher_id}_bookmark_delete_{bookmark.id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"teacher_{teacher_id}_play_lesson_{lesson_id}")]
    ])

    await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_bookmark_rename_\d+$"))
@user_required_callback
async def teacher_bookmark_rename_start(callback: CallbackQuery, state: FSMContext, user):
    """Начало переименования закладки (из навигации преподавателей)"""
    parts = callback.data.split("_")
    teacher_id = int(parts[1])  # teacher_X_bookmark_rename_Y
    bookmark_id = int(parts[4])

    bookmark = await get_bookmark_by_id(bookmark_id)

    if not bookmark or bookmark.user_id != user.id:
        await callback.answer("❌ Закладка не найдена", show_alert=True)
        return

    # Сохраняем данные с teacher_id для возврата
    await state.update_data(
        bookmark_id=bookmark_id,
        teacher_id=teacher_id,
        rename_message_id=callback.message.message_id,
        rename_chat_id=callback.message.chat.id
    )
    await state.set_state(BookmarkStates.renaming)

    text = (
        "✏️ <b>Переименование закладки</b>\n\n"
        f"Текущее название:\n"
        f"\"{bookmark.custom_name}\"\n\n"
        "Введите новое название:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"teacher_{teacher_id}_remove_bookmark_{bookmark.lesson_id}")]
    ])

    await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_bookmark_delete_\d+$") & ~F.data.regexp(r"^teacher_\d+_bookmark_delete_confirm_\d+$"))
@user_required_callback
async def teacher_bookmark_delete_confirm(callback: CallbackQuery, state: FSMContext, user):
    """Подтверждение удаления закладки (из навигации преподавателей)"""
    await state.clear()

    parts = callback.data.split("_")
    teacher_id = int(parts[1])  # teacher_X_bookmark_delete_Y
    bookmark_id = int(parts[4])

    bookmark = await get_bookmark_by_id(bookmark_id)

    if not bookmark or bookmark.user_id != user.id:
        await callback.answer("❌ Закладка не найдена", show_alert=True)
        return

    text = (
        "🗑️ <b>Удаление закладки</b>\n\n"
        "Вы уверены, что хотите удалить закладку?\n\n"
        f"📌 \"{bookmark.custom_name}\""
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"teacher_{teacher_id}_bookmark_delete_confirm_{bookmark_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"teacher_{teacher_id}_remove_bookmark_{bookmark.lesson_id}")]
    ])

    await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^teacher_\d+_bookmark_delete_confirm_\d+$"))
@user_required_callback
async def teacher_bookmark_delete_execute(callback: CallbackQuery, state: FSMContext, user):
    """Выполнение удаления закладки (из навигации преподавателей)"""
    await state.clear()

    parts = callback.data.split("_")
    teacher_id = int(parts[1])  # teacher_X_bookmark_delete_confirm_Y
    bookmark_id = int(parts[5])

    bookmark = await get_bookmark_by_id(bookmark_id)

    if not bookmark or bookmark.user_id != user.id:
        await callback.answer("❌ Закладка не найдена", show_alert=True)
        return

    lesson_id = bookmark.lesson_id

    # Удаляем закладку
    success = await delete_bookmark(bookmark_id)

    if success:
        text = "✅ <b>Закладка удалена</b>"
    else:
        text = "❌ Ошибка при удалении закладки"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К уроку", callback_data=f"teacher_{teacher_id}_play_lesson_{lesson_id}")]
    ])

    await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    await callback.answer()


# ==================== ТЕСТЫ С КОНТЕКСТОМ ПРЕПОДАВАТЕЛЯ ====================

@router.callback_query(F.data.regexp(r"^teacher_\d+_lesson_test_\d+$"))
@user_required_callback
async def teacher_lesson_test(callback: CallbackQuery, state: FSMContext):
    """Начать тест по конкретному уроку (из навигации преподавателей)"""
    parts = callback.data.split("_")
    teacher_id = int(parts[1])  # teacher_X_lesson_test_Y
    lesson_id = int(parts[4])

    # Сохраняем teacher_id в FSM для возврата после теста
    await state.update_data(teacher_id=teacher_id)

    # Перенаправляем на общую функцию теста урока
    from bot.handlers.user.tests import show_test_after_lesson
    from copy import copy
    new_callback = copy(callback)
    object.__setattr__(new_callback, 'data', f"test_after_lesson_{lesson_id}")
    await show_test_after_lesson(new_callback, state)


@router.callback_query(F.data.regexp(r"^teacher_\d+_start_test_\d+_\d+$"))
@user_required_callback
async def teacher_start_test(callback: CallbackQuery, state: FSMContext):
    """Запустить тест (из навигации преподавателей) - кнопка 'Пройти ещё раз'"""
    parts = callback.data.split("_")
    # teacher_X_start_test_Y_Z разбивается на: ['teacher', 'X', 'start', 'test', 'Y', 'Z']
    teacher_id = int(parts[1])  # X
    test_id = int(parts[4])     # Y
    lesson_id = int(parts[5])   # Z

    # Сохраняем teacher_id в FSM для возврата после теста
    await state.update_data(teacher_id=teacher_id)

    # Перенаправляем на общую функцию запуска теста
    from bot.handlers.user.tests import start_test
    from copy import copy
    new_callback = copy(callback)
    object.__setattr__(new_callback, 'data', f"start_test_{test_id}_{lesson_id}")
    await start_test(new_callback, state)


@router.callback_query(F.data.regexp(r"^teacher_\d+_general_test_\d+$"))
@user_required_callback
async def teacher_general_test(callback: CallbackQuery, state: FSMContext):
    """Показать общий тест по всей серии (из навигации преподавателей)"""
    parts = callback.data.split("_")
    teacher_id = int(parts[1])  # teacher_X_general_test_Y
    series_id = int(parts[4])

    # Сохраняем teacher_id в FSM для возврата после теста
    await state.update_data(teacher_id=teacher_id)

    # Перенаправляем на общую функцию теста серии
    from bot.handlers.user.tests import show_general_test
    from copy import copy
    new_callback = copy(callback)
    object.__setattr__(new_callback, 'data', f"general_test_{series_id}")
    await show_general_test(new_callback, state)
