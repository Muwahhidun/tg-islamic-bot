"""
Управление преподавателями
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required
from bot.services.database_service import (
    get_all_lesson_teachers,
    get_lesson_teacher_by_id,
    create_lesson_teacher,
    update_lesson_teacher,
    delete_lesson_teacher,
    get_all_lessons,
    get_all_books,
)

router = Router()


class LessonTeacherStates(StatesGroup):
    """Состояния для управления преподавателями"""
    name = State()
    biography = State()
    edit_series_year = State()
    edit_series_name = State()


@router.callback_query(F.data == "admin_teachers")
@admin_required
async def admin_teachers(callback: CallbackQuery):
    """Показать список преподавателей для управления"""
    teachers = await get_all_lesson_teachers()

    builder = InlineKeyboardBuilder()
    for teacher in teachers:
        status = "✅" if teacher.is_active else "❌"
        builder.add(InlineKeyboardButton(
            text=f"{status} {teacher.name}",
            callback_data=f"edit_teacher_{teacher.id}"
        ))

    builder.add(InlineKeyboardButton(text="➕ Добавить преподавателя", callback_data="add_teacher"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)

    await callback.message.edit_text(
        "👤 <b>Управление преподавателями</b>\n\n"
        "Выберите преподавателя для редактирования или добавьте нового:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_teacher")
@admin_required
async def add_teacher_start(callback: CallbackQuery, state: FSMContext):
    """Начать добавление нового преподавателя"""
    await callback.message.edit_text(
        "📝 <b>Добавление нового преподавателя</b>\n\n"
        "Введите имя преподавателя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_teachers")]])
    )
    await state.set_state(LessonTeacherStates.name)
    await callback.answer()


@router.callback_query(F.data.regexp(r"^edit_teacher_\d+$"))
@admin_required
async def edit_teacher_menu(callback: CallbackQuery):
    """Показать меню редактирования преподавателя"""
    teacher_id = int(callback.data.split("_")[2])
    teacher = await get_lesson_teacher_by_id(teacher_id)

    if not teacher:
        await callback.answer("❌ Преподаватель не найден")
        return

    status = "✅ Активен" if teacher.is_active else "❌ Неактивен"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Изменить имя", callback_data=f"edit_teacher_name_{teacher.id}"))
    builder.add(InlineKeyboardButton(text="📝 Изменить биографию", callback_data=f"edit_teacher_bio_{teacher.id}"))
    builder.add(InlineKeyboardButton(text="📚 Управление сериями", callback_data=f"manage_teacher_series_{teacher.id}"))
    builder.add(InlineKeyboardButton(text=f"🔄 Статус: {status}", callback_data=f"toggle_teacher_{teacher.id}"))
    builder.add(InlineKeyboardButton(text="🗑️ Удалить преподавателя", callback_data=f"delete_teacher_{teacher.id}"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_teachers"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"👤 <b>Редактирование преподавателя</b>\n\n"
        f"Имя: {teacher.name}\n"
        f"Биография: {teacher.biography or 'Нет биографии'}\n"
        f"Статус: {status}",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_teacher_"))
@admin_required
async def toggle_teacher(callback: CallbackQuery):
    """Переключить статус преподавателя"""
    teacher_id = int(callback.data.split("_")[2])
    teacher = await get_lesson_teacher_by_id(teacher_id)

    if not teacher:
        await callback.answer("❌ Преподаватель не найден")
        return

    teacher.is_active = not teacher.is_active
    await update_lesson_teacher(teacher)

    status = "активирован" if teacher.is_active else "деактивирован"
    await callback.answer(f"✅ Преподаватель {status}")

    # Обновляем меню редактирования - показываем заново
    teacher = await get_lesson_teacher_by_id(teacher_id)
    status_text = "✅ Активен" if teacher.is_active else "❌ Неактивен"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✏️ Изменить имя", callback_data=f"edit_teacher_name_{teacher.id}"))
    builder.add(InlineKeyboardButton(text="📝 Изменить биографию", callback_data=f"edit_teacher_bio_{teacher.id}"))
    builder.add(InlineKeyboardButton(text=f"🔄 Статус: {status_text}", callback_data=f"toggle_teacher_{teacher.id}"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_teachers"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"👤 <b>Редактирование преподавателя</b>\n\n"
        f"Имя: {teacher.name}\n"
        f"Биография: {teacher.biography or 'Нет биографии'}\n"
        f"Статус: {status_text}",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("delete_teacher_"))
@admin_required
async def delete_teacher_prompt(callback: CallbackQuery):
    """Подтверждение удаления преподавателя"""
    teacher_id = int(callback.data.split("_")[2])
    teacher = await get_lesson_teacher_by_id(teacher_id)

    if not teacher:
        await callback.answer("❌ Преподаватель не найден", show_alert=True)
        return

    # Подсчитываем количество уроков
    from bot.services.database_service import get_all_lessons
    lessons = await get_all_lessons()
    lessons_count = len([l for l in lessons if l.teacher_id == teacher_id])

    # Формируем предупреждение
    warning_text = f"⚠️ <b>Удаление преподавателя</b>\n\n"
    warning_text += f"Вы уверены, что хотите удалить преподавателя «{teacher.name}»?\n\n"

    if lessons_count > 0:
        warning_text += f"ℹ️ <b>У этого преподавателя есть {lessons_count} урок(ов)</b>\n"
        warning_text += "Уроки останутся в системе, но будут отвязаны от преподавателя.\n\n"

    warning_text += "Это действие нельзя отменить!"

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_teacher_{teacher_id}"))
    builder.add(InlineKeyboardButton(text="❌ Отмена", callback_data=f"edit_teacher_{teacher_id}"))
    builder.adjust(1)

    await callback.message.edit_text(warning_text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_delete_teacher_"))
@admin_required
async def confirm_delete_teacher(callback: CallbackQuery):
    """Подтвердить удаление преподавателя"""
    teacher_id = int(callback.data.split("_")[3])
    teacher = await get_lesson_teacher_by_id(teacher_id)

    if not teacher:
        await callback.answer("❌ Преподаватель не найден", show_alert=True)
        return

    teacher_name = teacher.name
    await delete_lesson_teacher(teacher_id)

    await callback.message.edit_text(
        f"✅ Преподаватель «{teacher_name}» удален",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 К списку преподавателей", callback_data="admin_teachers")
        ]])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_teacher_name_"))
@admin_required
async def edit_teacher_name_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование имени преподавателя"""
    teacher_id = int(callback.data.split("_")[3])
    teacher = await get_lesson_teacher_by_id(teacher_id)

    if not teacher:
        await callback.answer("❌ Преподаватель не найден")
        return

    # Сохраняем ID преподавателя в состоянии
    await state.update_data(teacher_id=teacher_id)

    await callback.message.edit_text(
        f"📝 <b>Редактирование имени преподавателя</b>\n\n"
        f"Текущее имя: {teacher.name}\n\n"
        f"Введите новое имя преподавателя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_teacher_{teacher_id}")
        ]])
    )
    await state.set_state(LessonTeacherStates.name)
    await callback.answer()


@router.message(LessonTeacherStates.name)
@admin_required
async def edit_teacher_name_save(message: Message, state: FSMContext):
    """Сохранить новое имя преподавателя"""
    data = await state.get_data()
    teacher_id = data.get("teacher_id")

    # Проверяем, это редактирование или создание
    if teacher_id:
        # Редактирование существующего преподавателя
        teacher = await get_lesson_teacher_by_id(teacher_id)
        if teacher:
            teacher.name = message.text
            await update_lesson_teacher(teacher)

            await message.answer(
                f"✅ Имя преподавателя успешно изменено на «{message.text}»!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 К преподавателю", callback_data=f"edit_teacher_{teacher_id}")
                ]])
            )
            await state.clear()
        else:
            await message.answer("❌ Преподаватель не найден")
            await state.clear()
    else:
        # Это создание нового преподавателя
        await state.update_data(name=message.text)

        await message.answer(
            "📝 <b>Добавление нового преподавателя</b>\n\n"
            "Введите биографию преподавателя:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_teacher_biography")],
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_teachers")]
            ])
        )
        await state.set_state(LessonTeacherStates.biography)


@router.callback_query(F.data.startswith("edit_teacher_bio_"))
@admin_required
async def edit_teacher_bio_start(callback: CallbackQuery, state: FSMContext):
    """Начать редактирование биографии преподавателя"""
    teacher_id = int(callback.data.split("_")[3])
    teacher = await get_lesson_teacher_by_id(teacher_id)

    if not teacher:
        await callback.answer("❌ Преподаватель не найден")
        return

    # Сохраняем ID преподавателя в состоянии
    await state.update_data(teacher_id=teacher_id)

    await callback.message.edit_text(
        f"📝 <b>Редактирование биографии преподавателя</b>\n\n"
        f"Текущая биография: {teacher.biography or 'Нет биографии'}\n\n"
        f"Введите новую биографию преподавателя:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Удалить биографию", callback_data="skip_teacher_biography")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_teacher_{teacher_id}")]
        ])
    )
    await state.set_state(LessonTeacherStates.biography)
    await callback.answer()


@router.callback_query(F.data == "skip_teacher_biography")
@admin_required
async def skip_teacher_biography(callback: CallbackQuery, state: FSMContext):
    """Удалить биографию преподавателя или пропустить при создании"""
    data = await state.get_data()
    teacher_id = data.get("teacher_id")

    # Проверяем, это редактирование или создание
    if teacher_id:
        # Редактирование - удаляем биографию
        teacher = await get_lesson_teacher_by_id(teacher_id)
        if teacher:
            teacher.biography = ""
            await update_lesson_teacher(teacher)

            await callback.message.edit_text(
                "✅ Биография преподавателя удалена!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 К преподавателю", callback_data=f"edit_teacher_{teacher_id}")
                ]])
            )
            await state.clear()
        else:
            await callback.answer("❌ Преподаватель не найден", show_alert=True)
            await state.clear()
    else:
        # Это создание нового преподавателя
        name = data.get("name")

        teacher = await create_lesson_teacher(
            name=name,
            biography="",
            is_active=True
        )

        await callback.message.edit_text(
            f"✅ Преподаватель «{teacher.name}» успешно добавлен!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К списку преподавателей", callback_data="admin_teachers")
            ]])
        )
        await state.clear()
    await callback.answer()


@router.message(LessonTeacherStates.biography)
@admin_required
async def edit_teacher_bio_save(message: Message, state: FSMContext):
    """Сохранить новую биографию преподавателя"""
    data = await state.get_data()
    teacher_id = data.get("teacher_id")

    # Проверяем, это редактирование или создание
    if teacher_id:
        # Редактирование существующего преподавателя
        teacher = await get_lesson_teacher_by_id(teacher_id)
        if teacher:
            teacher.biography = message.text
            await update_lesson_teacher(teacher)

            await message.answer(
                f"✅ Биография преподавателя успешно изменена!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="🔙 К преподавателю", callback_data=f"edit_teacher_{teacher_id}")
                ]])
            )
            await state.clear()
        else:
            await message.answer("❌ Преподаватель не найден")
            await state.clear()
    else:
        # Это создание нового преподавателя
        name = data.get("name")

        teacher = await create_lesson_teacher(
            name=name,
            biography=message.text,
            is_active=True
        )

        await message.answer(
            f"✅ Преподаватель «{teacher.name}» успешно добавлен!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 К списку преподавателей", callback_data="admin_teachers")
            ]])
        )
        await state.clear()
