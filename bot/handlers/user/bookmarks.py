"""
Обработчики для работы с закладками пользователей
"""
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import user_required_callback
from bot.states.bookmark_states import BookmarkStates
from bot.services.database_service import (
    get_bookmarks_by_user,
    get_bookmark_by_id,
    get_bookmark_by_user_and_lesson,
    count_user_bookmarks,
    create_bookmark,
    update_bookmark_name,
    delete_bookmark,
    get_lesson_by_id
)

logger = logging.getLogger(__name__)
router = Router()

# Лимит закладок на пользователя
MAX_BOOKMARKS = 20


# ==================== СПИСОК ЗАКЛАДОК ====================

@router.callback_query(F.data == "bookmarks")
@user_required_callback
async def show_bookmarks_list(callback: CallbackQuery, state: FSMContext, user):
    """Показать список закладок пользователя"""
    await state.clear()

    bookmarks = await get_bookmarks_by_user(user.id)

    if not bookmarks:
        # Пустой список закладок
        text = (
            "📌 <b>Мои закладки</b>\n\n"
            "📭 У вас пока нет сохранённых закладок.\n\n"
            "💡 Добавьте закладку на любой урок, нажав кнопку\n"
            "\"➕ Добавить в закладки\" во время прослушивания."
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚 К темам", callback_data="show_themes")],
            [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="main_menu")]
        ])

        # Удаляем старое сообщение и отправляем новое (может быть аудио с caption)
        try:
            await callback.message.delete()
        except:
            pass

        await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
        return

    # Формируем список закладок
    text = f"📌 <b>Мои закладки</b>\n\n<b>Всего:</b> {len(bookmarks)}\n\nВыберите закладку для просмотра:"

    # Создаём клавиатуру с кнопками закладок
    builder = InlineKeyboardBuilder()

    for i, bookmark in enumerate(bookmarks, 1):
        date_str = bookmark.created_at.strftime('%d.%m.%Y')
        builder.add(InlineKeyboardButton(
            text=f"{i}️⃣ {bookmark.custom_name} | 📅 {date_str}",
            callback_data=f"bookmark_{bookmark.id}"
        ))

    builder.adjust(1)  # По одной кнопке в строке

    builder.row(InlineKeyboardButton(
        text="⬅️ Главное меню",
        callback_data="main_menu"
    ))

    # Удаляем старое сообщение и отправляем новое (может быть аудио с caption)
    try:
        await callback.message.delete()
    except:
        pass

    await callback.message.answer(text, reply_markup=builder.as_markup())
    await callback.answer()


# ==================== ДЕТАЛИ ЗАКЛАДКИ ====================

@router.callback_query(F.data.startswith("bookmark_") & ~F.data.startswith("bookmark_open_")
                       & ~F.data.startswith("bookmark_rename_") & ~F.data.startswith("bookmark_delete_"))
@user_required_callback
async def show_bookmark_details(callback: CallbackQuery, state: FSMContext, user):
    """Показать детали закладки с кнопками действий"""
    await state.clear()

    bookmark_id = int(callback.data.split("_")[1])
    bookmark = await get_bookmark_by_id(bookmark_id)

    if not bookmark:
        await callback.answer("❌ Закладка не найдена", show_alert=True)
        return

    # Проверяем, что закладка принадлежит пользователю
    if bookmark.user_id != user.id:
        await callback.answer("❌ Нет доступа к этой закладке", show_alert=True)
        return

    lesson = bookmark.lesson

    # Формируем текст с полной информацией
    text = f"📌 <b>Закладка: \"{bookmark.custom_name}\"</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"🎧 <b>Урок {lesson.lesson_number}:</b> {lesson.title}\n\n"

    # Тема
    if lesson.book and lesson.book.theme:
        text += f"📚 Тема: {lesson.book.theme.name}\n"

    # Книга
    if lesson.book:
        text += f"📖 Книга: «{lesson.book.name}»\n"

    # Автор книги
    if lesson.book and lesson.book.author:
        text += f"✍️ Автор: {lesson.book.author.name}\n"

    # Преподаватель
    if lesson.teacher:
        text += f"🎙️ Преподаватель: {lesson.teacher.name}\n"

    # Серия
    if lesson.series:
        text += f"📁 Серия: {lesson.series.display_name}\n"

    text += f"\n📅 Добавлено: {bookmark.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "Выберите действие:"

    # Создаём клавиатуру с действиями
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎧 Открыть урок", callback_data=f"bookmark_open_{bookmark_id}")],
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"bookmark_rename_{bookmark_id}")],
        [InlineKeyboardButton(text="🗑️ Удалить закладку", callback_data=f"bookmark_delete_{bookmark_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к закладкам", callback_data="bookmarks")]
    ])

    # Пробуем edit_caption (если сообщение с аудио), если не получится - edit_text
    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    except:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


# ==================== ОТКРЫТЬ УРОК ИЗ ЗАКЛАДКИ ====================

@router.callback_query(F.data.startswith("bookmark_open_"))
@user_required_callback
async def open_lesson_from_bookmark(callback: CallbackQuery, state: FSMContext, user):
    """Открыть урок из закладки"""
    await state.clear()

    bookmark_id = int(callback.data.split("_")[2])
    bookmark = await get_bookmark_by_id(bookmark_id)

    if not bookmark or bookmark.user_id != user.id:
        await callback.answer("❌ Закладка не найдена", show_alert=True)
        return

    # Перенаправляем на обработчик урока
    from copy import copy
    new_callback = copy(callback)
    object.__setattr__(new_callback, 'data', f"lesson_{bookmark.lesson_id}")

    from bot.handlers.user.lessons import play_lesson
    await play_lesson(new_callback)


# ==================== ДОБАВЛЕНИЕ ЗАКЛАДКИ ====================

@router.callback_query(F.data.startswith("add_bookmark_"))
@user_required_callback
async def add_bookmark_start(callback: CallbackQuery, state: FSMContext, user):
    """Начало добавления закладки - запрос названия"""
    lesson_id = int(callback.data.split("_")[2])

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
            [InlineKeyboardButton(text="⬅️ К уроку", callback_data=f"lesson_{lesson_id}")]
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
        bookmark_message_id=callback.message.message_id,
        bookmark_chat_id=callback.message.chat.id
    )
    await state.set_state(BookmarkStates.entering_name)

    text = (
        "📌 <b>Добавление в закладки</b>\n\n"
        f"🎧 Урок {lesson.lesson_number}: {lesson.title}\n"
    )

    if lesson.book and lesson.book.theme:
        text += f"📚 Тема: {lesson.book.theme.name}\n"
    if lesson.book:
        text += f"📖 Книга: «{lesson.book.name}»\n"

    text += "\nВведите название закладки:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"lesson_{lesson_id}")]
    ])

    await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    await callback.answer()


@router.message(BookmarkStates.entering_name)
async def add_bookmark_save(message: Message, state: FSMContext):
    """Сохранение закладки после ввода названия"""
    data = await state.get_data()
    lesson_id = data.get("lesson_id")
    message_id = data.get("bookmark_message_id")
    chat_id = data.get("bookmark_chat_id")

    custom_name = message.text.strip()

    # Проверка длины названия
    if len(custom_name) > 200:
        custom_name = custom_name[:200]

    if not custom_name:
        await message.delete()
        await message.answer("❌ Название не может быть пустым. Попробуйте ещё раз:")
        return

    # Удаляем сообщение пользователя (паттерн одного окна)
    try:
        await message.delete()
    except:
        pass

    # Получаем пользователя по telegram_id
    from bot.services.database_service import get_user_by_telegram_id
    user = await get_user_by_telegram_id(message.from_user.id)

    if not user:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    # Создаём закладку
    try:
        bookmark = await create_bookmark(
            user_id=user.id,  # database user_id
            lesson_id=lesson_id,
            custom_name=custom_name
        )

        text = (
            "✅ <b>Закладка сохранена!</b>\n\n"
            f"📌 \"{custom_name}\""
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📌 Мои закладки", callback_data="bookmarks")],
            [InlineKeyboardButton(text="⬅️ К уроку", callback_data=f"lesson_{lesson_id}")]
        ])

        # Обновляем исходное сообщение
        await message.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=text,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Ошибка создания закладки: {e}")
        text = "❌ Ошибка при сохранении закладки. Попробуйте позже."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К уроку", callback_data=f"lesson_{lesson_id}")]
        ])
        await message.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=text,
            reply_markup=keyboard
        )

    await state.clear()


# ==================== ПЕРЕИМЕНОВАНИЕ ЗАКЛАДКИ ====================

@router.callback_query(F.data.startswith("bookmark_rename_"))
@user_required_callback
async def rename_bookmark_start(callback: CallbackQuery, state: FSMContext, user):
    """Начало переименования закладки"""
    bookmark_id = int(callback.data.split("_")[2])
    bookmark = await get_bookmark_by_id(bookmark_id)

    if not bookmark or bookmark.user_id != user.id:
        await callback.answer("❌ Закладка не найдена", show_alert=True)
        return

    # Сохраняем данные
    await state.update_data(
        bookmark_id=bookmark_id,
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
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"bookmark_{bookmark_id}")]
    ])

    await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    await callback.answer()


@router.message(BookmarkStates.renaming)
async def rename_bookmark_save(message: Message, state: FSMContext):
    """Сохранение нового названия закладки"""
    data = await state.get_data()
    bookmark_id = data.get("bookmark_id")
    message_id = data.get("rename_message_id")
    chat_id = data.get("rename_chat_id")

    new_name = message.text.strip()

    # Проверка длины
    if len(new_name) > 200:
        new_name = new_name[:200]

    if not new_name:
        await message.delete()
        await message.answer("❌ Название не может быть пустым. Попробуйте ещё раз:")
        return

    # Удаляем сообщение пользователя (паттерн одного окна)
    try:
        await message.delete()
    except:
        pass

    # Обновляем название
    try:
        bookmark = await update_bookmark_name(bookmark_id, new_name)

        if bookmark:
            text = (
                "✅ <b>Закладка переименована!</b>\n\n"
                f"Новое название:\n"
                f"📌 \"{new_name}\""
            )
        else:
            text = "❌ Закладка не найдена"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к закладке", callback_data=f"bookmark_{bookmark_id}")]
        ])

        await message.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=text,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Ошибка переименования закладки: {e}")
        text = "❌ Ошибка при переименовании. Попробуйте позже."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"bookmark_{bookmark_id}")]
        ])
        await message.bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=text,
            reply_markup=keyboard
        )

    await state.clear()


# ==================== УДАЛЕНИЕ ЗАКЛАДКИ ====================

@router.callback_query(F.data.startswith("bookmark_delete_") & ~F.data.startswith("bookmark_delete_confirm_"))
@user_required_callback
async def delete_bookmark_confirm(callback: CallbackQuery, state: FSMContext, user):
    """Подтверждение удаления закладки"""
    await state.clear()

    bookmark_id = int(callback.data.split("_")[2])
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
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"bookmark_delete_confirm_{bookmark_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"bookmark_{bookmark_id}")]
    ])

    await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("bookmark_delete_confirm_"))
@user_required_callback
async def delete_bookmark_execute(callback: CallbackQuery, state: FSMContext, user):
    """Выполнение удаления закладки"""
    await state.clear()

    bookmark_id = int(callback.data.split("_")[3])
    bookmark = await get_bookmark_by_id(bookmark_id)

    if not bookmark or bookmark.user_id != user.id:
        await callback.answer("❌ Закладка не найдена", show_alert=True)
        return

    # Удаляем закладку
    success = await delete_bookmark(bookmark_id)

    if success:
        text = "✅ <b>Закладка удалена</b>"
    else:
        text = "❌ Ошибка при удалении закладки"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📌 Мои закладки", callback_data="bookmarks")]
    ])

    await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    await callback.answer()


# ==================== УДАЛЕНИЕ ЗАКЛАДКИ С ЭКРАНА УРОКА ====================

@router.callback_query(F.data.startswith("remove_bookmark_"))
@user_required_callback
async def remove_bookmark_from_lesson(callback: CallbackQuery, state: FSMContext, user):
    """Удалить закладку прямо с экрана урока (показать меню управления)"""
    lesson_id = int(callback.data.split("_")[2])

    # Находим закладку
    bookmark = await get_bookmark_by_user_and_lesson(user.id, lesson_id)

    if not bookmark:
        await callback.answer("❌ Закладка не найдена", show_alert=True)
        return

    # Показываем меню управления закладкой (как в show_bookmark_details)
    lesson = bookmark.lesson

    text = f"📌 <b>Закладка: \"{bookmark.custom_name}\"</b>\n\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    text += f"🎧 <b>Урок {lesson.lesson_number}:</b> {lesson.title}\n\n"

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

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"bookmark_rename_{bookmark.id}")],
        [InlineKeyboardButton(text="🗑️ Удалить закладку", callback_data=f"bookmark_delete_{bookmark.id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"lesson_{lesson_id}")]
    ])

    await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    await callback.answer()
