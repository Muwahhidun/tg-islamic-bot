"""
Управление темами
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required
from bot.services.database_service import (
    get_all_themes,
    get_theme_by_id,
    create_theme,
    update_theme,
    delete_theme,
)

router = Router()


class ThemeStates(StatesGroup):
    """Состояния для управления темами"""
    name = State()
    description = State()


@router.callback_query(F.data == "admin_themes")
@admin_required
async def admin_themes(callback: CallbackQuery):
    """Показать список тем для управления"""
    themes = await get_all_themes()

    builder = InlineKeyboardBuilder()
    for theme in themes:
        status = "✅" if theme.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {theme.name}",
            callback_data=f"edit_theme_{theme.id}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить тему", callback_data="add_theme"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)

    await callback.message.edit_text(
        "📚 <b>Управление темами</b>\n\n"
        "Выберите тему для редактирования или добавьте новую:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_theme")
@admin_required
async def add_theme_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление новой темы"""
    await callback.message.edit_text(
        "📝 <b>Добавление новой темы</b>\n\n"
        "Введите название темы:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_themes")]])
    )
    await state.set_state(ThemeStates.name)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^edit_theme_\d+$"))
@admin_required
async def edit_theme_menu(callback: CallbackQuery):
    """Показать меню редактирования темы"""
    theme_id = int(callback.data.split("_")[2])
    theme = await get_theme_by_id(theme_id)

    if not theme:
        await callback.answer("❌ Тема не найдена")
        return

    status = "✅ Активна" if theme.is_active else "❌ Неактивна"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"edit_theme_name_{theme.id}"))
    builder.add(InlineKeyboardButton(text="📝 Изменить описание", callback_data=f"edit_theme_desc_{theme.id}"))
    builder.add(InlineKeyboardButton(text=f"🔄 Статус: {status}", callback_data=f"toggle_theme_{theme.id}"))
    builder.add(InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_theme_{theme.id}"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_themes"))
    builder.adjust(2)

    await callback.message.edit_text(
        f"📚 <b>Редактирование темы</b>\n\n"
        f"Название: {theme.name}\n"
        f"Описание: {theme.description or 'Нет описания'}\n"
        f"Статус: {status}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_theme_"))
@admin_required
async def toggle_theme(callback: CallbackQuery):
    """Переключить статус темы"""
    theme_id = int(callback.data.split("_")[2])
    theme = await get_theme_by_id(theme_id)

    if not theme:
        await callback.answer("❌ Тема не найдена")
        return

    theme.is_active = not theme.is_active
    await update_theme(theme)

    status = "активирована" if theme.is_active else "деактивирована"
    await callback.answer(f"✅ Тема {status}")

    # Rebuild menu with updated status
    status_text = "✅ Активна" if theme.is_active else "❌ Неактивна"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"edit_theme_name_{theme.id}"))
    builder.add(InlineKeyboardButton(text="📝 Изменить описание", callback_data=f"edit_theme_desc_{theme.id}"))
    builder.add(InlineKeyboardButton(text=f"🔄 Статус: {status_text}", callback_data=f"toggle_theme_{theme.id}"))
    builder.add(InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_theme_{theme.id}"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_themes"))
    builder.adjust(2)

    await callback.message.edit_text(
        f"📚 <b>Редактирование темы</b>\n\n"
        f"Название: {theme.name}\n"
        f"Описание: {theme.description or 'Нет описания'}\n"
        f"Статус: {status_text}",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("edit_theme_name_"))
@admin_required
async def edit_theme_name_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование названия темы"""
    theme_id = int(callback.data.split("_")[3])
    theme = await get_theme_by_id(theme_id)

    if not theme:
        await callback.answer("❌ Тема не найдена")
        return

    await state.update_data(theme_id=theme_id)

    await callback.message.edit_text(
        f"📝 <b>Редактирование названия темы</b>\n\n"
        f"Текущее название: {theme.name}\n\n"
        f"Введите новое название темы:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_theme_{theme_id}")
        ]])
    )
    await state.set_state(ThemeStates.name)
    await callback.answer()


@router.message(ThemeStates.name)
@admin_required
async def edit_theme_name_save(message: Message, state: FSMContext):
    """Сохранить новое название темы"""
    data = await state.get_data()
    theme_id = data.get("theme_id")

    if theme_id:
        # Редактирование существующей темы
        theme = await get_theme_by_id(theme_id)
        if theme:
            theme.name = message.text
            await update_theme(theme)

            await message.answer(
                f"✅ Название темы успешно изменено на «{message.text}»!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 К теме", callback_data=f"edit_theme_{theme_id}")
                ]])
            )
            await state.clear()
        else:
            await message.answer("❌ Тема не найдена")
            await state.clear()
    else:
        # Это создание новой темы
        await state.update_data(name=message.text)
        await message.answer(
            "📝 <b>Добавление новой темы</b>\n\n"
            "Введите описание темы:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_theme_description")],
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_themes")]
            ])
        )
        await state.set_state(ThemeStates.description)


@router.callback_query(F.data.startswith("edit_theme_desc_"))
@admin_required
async def edit_theme_desc_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование описания темы"""
    theme_id = int(callback.data.split("_")[3])
    theme = await get_theme_by_id(theme_id)

    if not theme:
        await callback.answer("❌ Тема не найдена")
        return

    await state.update_data(theme_id=theme_id, editing_description=True)

    await callback.message.edit_text(
        f"📝 <b>Редактирование описания темы</b>\n\n"
        f"Текущее описание: {theme.description or 'Нет описания'}\n\n"
        f"Введите новое описание темы:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Удалить описание", callback_data="skip_theme_description")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_theme_{theme_id}")]
        ])
    )
    await state.set_state(ThemeStates.description)
    await callback.answer()


@router.callback_query(F.data == "skip_theme_description")
@admin_required
async def skip_theme_description(callback: CallbackQuery, state: FSMContext):
    """Пропустить/удалить описание темы"""
    data = await state.get_data()
    theme_id = data.get("theme_id")
    editing_description = data.get("editing_description", False)

    if theme_id and editing_description:
        # Редактирование - удаляем описание
        theme = await get_theme_by_id(theme_id)
        if theme:
            theme.description = ""
            await update_theme(theme)

            await callback.message.edit_text(
                "✅ Описание темы удалено!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 К теме", callback_data=f"edit_theme_{theme_id}")
                ]])
            )
            await state.clear()
        else:
            await callback.answer("❌ Тема не найдена", show_alert=True)
            await state.clear()
    else:
        # Это создание новой темы - пропускаем описание
        name = data.get("name")
        theme = await create_theme(
            name=name,
            description="",
            is_active=True
        )

        await callback.message.edit_text(
            f"✅ Тема «{theme.name}» успешно добавлена!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К списку тем", callback_data="admin_themes")
            ]])
        )
        await state.clear()
    await callback.answer()


@router.message(ThemeStates.description)
@admin_required
async def edit_theme_desc_save(message: Message, state: FSMContext):
    """Сохранить новое описание темы"""
    data = await state.get_data()
    theme_id = data.get("theme_id")
    editing_description = data.get("editing_description", False)

    if theme_id and editing_description:
        # Редактирование существующей темы
        theme = await get_theme_by_id(theme_id)
        if theme:
            theme.description = message.text
            await update_theme(theme)

            await message.answer(
                f"✅ Описание темы успешно изменено!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 К теме", callback_data=f"edit_theme_{theme_id}")
                ]])
            )
            await state.clear()
        else:
            await message.answer("❌ Тема не найдена")
            await state.clear()
    else:
        # Это создание новой темы
        name = data.get("name")
        theme = await create_theme(
            name=name,
            description=message.text,
            is_active=True
        )

        await message.answer(
            f"✅ Тема «{theme.name}» успешно добавлена!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К списку тем", callback_data="admin_themes")
            ]])
        )
        await state.clear()


@router.callback_query(F.data.startswith("delete_theme_"))
@admin_required
async def delete_theme_prompt(callback: CallbackQuery):
    """Подтверждение удаления темы"""
    theme_id = int(callback.data.split("_")[2])
    theme = await get_theme_by_id(theme_id)

    if not theme:
        await callback.answer("❌ Тема не найдена")
        return

    # Подсчет статистики для предупреждения
    books_count = len(theme.books) if theme.books else 0
    lessons_count = sum(len(book.lessons) if book.lessons else 0 for book in theme.books) if theme.books else 0

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_theme_{theme.id}"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_theme_{theme.id}"))

    # Формируем детальное предупреждение
    warning_text = f"⚠️ <b>Удаление темы</b>\n\n"
    warning_text += f"Вы уверены, что хотите удалить тему «{theme.name}»?\n\n"

    if books_count > 0:
        warning_text += f"ℹ️ <b>У этой темы есть {books_count} книг(и)</b>\n"
        warning_text += f"При удалении темы книги НЕ удалятся, но перейдут в категорию \"Без темы\".\n"
        if lessons_count > 0:
            warning_text += f"(в них {lessons_count} уроков)\n"
        warning_text += "\n"

    warning_text += "Это действие нельзя отменить!"

    await callback.message.edit_text(
        warning_text,
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_theme_"))
@admin_required
async def confirm_delete_theme(callback: CallbackQuery):
    """Подтвердить удаление темы"""
    theme_id = int(callback.data.split("_")[3])
    theme = await get_theme_by_id(theme_id)

    if not theme:
        await callback.answer("❌ Тема не найдена")
        return

    await delete_theme(theme_id)

    await callback.message.edit_text(
        f"✅ Тема «{theme.name}» и все связанные данные удалены",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 К списку тем", callback_data="admin_themes")]])
    )
    await callback.answer()


@router.callback_query(F.data == "admin_panel")
@admin_required
async def back_to_admin_panel(callback: CallbackQuery):
    """Вернуться в административную панель"""
    builder = InlineKeyboardBuilder()

    builder.add(InlineKeyboardButton(text="📚 Управление темами", callback_data="admin_themes"))
    builder.add(InlineKeyboardButton(text="✍️ Управление авторами", callback_data="admin_authors"))
    builder.add(InlineKeyboardButton(text="👨‍🏫 Управление преподавателями", callback_data="admin_teachers"))
    builder.add(InlineKeyboardButton(text="📖 Управление книгами", callback_data="admin_books"))
    builder.add(InlineKeyboardButton(text="🎧 Управление уроками", callback_data="admin_lessons"))
    builder.add(InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users"))
    builder.add(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.add(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))
    builder.adjust(1)

    await callback.message.edit_text(
        "🛠️ <b>Административная панель</b>\n\n"
        "Выберите раздел для управления:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()
