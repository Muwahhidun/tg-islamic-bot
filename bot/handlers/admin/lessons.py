"""
Обработчики управления уроками для администраторов
"""
import os

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required
from bot.services.database_service import (
    get_all_lessons,
    get_all_books,
    get_all_lesson_teachers,
    create_lesson
)

router = Router()


class LessonStates(StatesGroup):
    """Состояния для управления уроками"""
    title = State()
    description = State()
    book_id = State()
    teacher_id = State()
    lesson_number = State()
    duration_minutes = State()
    tags = State()
    audio_file = State()


@router.callback_query(F.data == "admin_lessons")
@admin_required
async def admin_lessons(callback: CallbackQuery):
    """Показать список уроков для управления"""
    lessons = await get_all_lessons()

    builder = InlineKeyboardBuilder()
    for lesson in lessons:
        status = "✅" if lesson.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} Урок {lesson.lesson_number}: {lesson.title}",
            callback_data=f"edit_lesson_{lesson.id}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить урок", callback_data="add_lesson"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)

    await callback.message.edit_text(
        "🎧 <b>Управление уроками</b>\n\n"
        "Выберите урок для редактирования или добавьте новый:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_lesson")
@admin_required
async def add_lesson_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление нового урока"""
    # Получаем список книг и преподавателей
    books = await get_all_books()
    teachers = await get_all_lesson_teachers()

    if not books or not teachers:
        await callback.message.edit_text(
            "❌ Для добавления урока нужно сначала создать хотя бы одну книгу и одного преподавателя",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_lessons")]])
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Введите название урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.title)
    await callback.answer()


@router.message(LessonStates.title)
@admin_required
async def add_lesson_title(message: Message, state: FSMContext):
    """Сохранить название урока"""
    await state.update_data(title=message.text)

    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Введите описание урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_lesson_description")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]
        ])
    )
    await state.set_state(LessonStates.description)


@router.callback_query(F.data == "skip_lesson_description")
@admin_required
async def add_lesson_skip_description(callback: CallbackQuery, state: FSMContext):
    """Пропустить описание урока"""
    data = await state.get_data()

    # Получаем список книг
    books = await get_all_books()

    builder = InlineKeyboardBuilder()
    for book in books:
        builder.add(InlineKeyboardButton(text=book.name, callback_data=f"select_book_{book.id}"))

    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Выберите книгу для урока:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(LessonStates.book_id)
    await callback.answer()


@router.message(LessonStates.description)
@admin_required
async def add_lesson_description(message: Message, state: FSMContext):
    """Сохранить описание урока"""
    await state.update_data(description=message.text)

    # Получаем список книг
    books = await get_all_books()

    builder = InlineKeyboardBuilder()
    for book in books:
        builder.add(InlineKeyboardButton(text=book.name, callback_data=f"select_book_{book.id}"))

    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Выберите книгу для урока:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(LessonStates.book_id)


@router.callback_query(F.data.startswith("select_book_"))
@admin_required
async def select_book_for_lesson(callback: CallbackQuery, state: FSMContext):
    """Выбрать книгу для урока"""
    book_id = int(callback.data.split("_")[2])
    await state.update_data(book_id=book_id)

    # Получаем список преподавателей
    teachers = await get_all_lesson_teachers()

    builder = InlineKeyboardBuilder()
    for teacher in teachers:
        builder.add(InlineKeyboardButton(text=teacher.name, callback_data=f"select_teacher_{teacher.id}"))

    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Выберите преподавателя урока:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(LessonStates.teacher_id)
    await callback.answer()


@router.callback_query(F.data.startswith("select_teacher_"))
@admin_required
async def select_teacher_for_lesson(callback: CallbackQuery, state: FSMContext):
    """Выбрать преподавателя для урока"""
    teacher_id = int(callback.data.split("_")[2])
    await state.update_data(teacher_id=teacher_id)

    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Введите номер урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.lesson_number)
    await callback.answer()


@router.message(LessonStates.lesson_number)
@admin_required
async def add_lesson_number(message: Message, state: FSMContext):
    """Сохранить номер урока"""
    try:
        lesson_number = int(message.text)
        await state.update_data(lesson_number=lesson_number)

        await message.answer(
            "📝 <b>Добавление нового урока</b>\n\n"
            "Введите длительность урока в минутах:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )
        await state.set_state(LessonStates.duration_minutes)
    except ValueError:
        await message.answer(
            "❌ Номер урока должен быть числом. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )


@router.message(LessonStates.duration_minutes)
@admin_required
async def add_lesson_duration(message: Message, state: FSMContext):
    """Сохранить длительность урока"""
    try:
        duration_minutes = int(message.text)
        await state.update_data(duration_minutes=duration_minutes)

        await message.answer(
            "📝 <b>Добавление нового урока</b>\n\n"
            "Введите теги для урока через запятую:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_lesson_tags")],
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]
            ])
        )
        await state.set_state(LessonStates.tags)
    except ValueError:
        await message.answer(
            "❌ Длительность должна быть числом. Попробуйте еще раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
        )


@router.callback_query(F.data == "skip_lesson_tags")
@admin_required
async def add_lesson_skip_tags(callback: CallbackQuery, state: FSMContext):
    """Пропустить теги урока"""
    await callback.message.edit_text(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Отправьте аудиофайл урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.audio_file)
    await callback.answer()


@router.message(LessonStates.tags)
@admin_required
async def add_lesson_tags(message: Message, state: FSMContext):
    """Сохранить теги урока"""
    await state.update_data(tags=message.text)

    await message.answer(
        "📝 <b>Добавление нового урока</b>\n\n"
        "Отправьте аудиофайл урока:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_lessons")]])
    )
    await state.set_state(LessonStates.audio_file)


@router.message(LessonStates.audio_file, F.audio)
@admin_required
async def add_lesson_audio(message: Message, state: FSMContext):
    """Сохранить аудиофайл урока"""
    data = await state.get_data()

    # Скачиваем аудиофайл
    audio_file = message.audio
    file_info = await message.bot.get_file(audio_file.file_id)
    downloaded_file = await message.bot.download_file(file_info.file_path)

    # Сохраняем файл
    audio_dir = "bot/audio_files"
    os.makedirs(audio_dir, exist_ok=True)

    file_path = os.path.join(audio_dir, f"{audio_file.file_unique_id}.mp3")
    with open(file_path, "wb") as f:
        f.write(downloaded_file.getvalue())

    lesson = await create_lesson(
        title=data["title"],
        description=data.get("description", ""),
        audio_file_path=file_path,
        duration_minutes=data["duration_minutes"],
        lesson_number=data["lesson_number"],
        book_id=data["book_id"],
        teacher_id=data["teacher_id"],
        tags=data.get("tags", ""),
        is_active=True
    )

    await message.answer(
        f"✅ Урок «{lesson.title}» успешно добавлен!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку уроков", callback_data="admin_lessons")]])
    )
    await state.clear()
