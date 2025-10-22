from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.states.feedback_states import FeedbackStates
from bot.services.database_service import (
    get_all_feedbacks,
    get_feedback_by_id,
    count_feedbacks_by_status,
    update_feedback_reply,
    close_feedback,
    delete_feedback
)
from bot.utils.decorators import admin_required
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "admin_feedbacks")
@admin_required
async def show_feedbacks_menu(callback: CallbackQuery, state: FSMContext):
    """Главное меню обращений для админа"""
    await state.clear()

    # Подсчитываем статусы
    new_count = await count_feedbacks_by_status("new")
    replied_count = await count_feedbacks_by_status("replied")
    closed_count = await count_feedbacks_by_status("closed")
    total_count = new_count + replied_count + closed_count

    text = (
        "📨 <b>Обращения пользователей</b>\n\n"
        f"Всего: {total_count}\n"
        f"🆕 Новых: {new_count}\n"
        f"✅ Отвечено: {replied_count}\n"
        f"🔒 Закрыто: {closed_count}\n\n"
        "Выберите фильтр:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🆕 Новые ({new_count})", callback_data="feedbacks_filter_new")],
        [InlineKeyboardButton(text=f"✅ Отвеченные ({replied_count})", callback_data="feedbacks_filter_replied")],
        [InlineKeyboardButton(text=f"🔒 Закрытые ({closed_count})", callback_data="feedbacks_filter_closed")],
        [InlineKeyboardButton(text=f"📋 Все ({total_count})", callback_data="feedbacks_filter_all")],
        [InlineKeyboardButton(text="⬅️ В админ-панель", callback_data="admin_panel")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("feedbacks_filter_"))
@admin_required
async def show_feedbacks_list(callback: CallbackQuery, state: FSMContext):
    """Показать список обращений по фильтру"""
    await state.clear()

    filter_type = callback.data.split("_")[2]  # new, replied, closed, all

    if filter_type == "all":
        feedbacks = await get_all_feedbacks()
        title = "📋 Все обращения"
    else:
        feedbacks = await get_all_feedbacks(status=filter_type)
        status_map = {
            "new": "🆕 Новые",
            "replied": "✅ Отвеченные",
            "closed": "🔒 Закрытые"
        }
        title = status_map.get(filter_type, "Обращения")

    if not feedbacks:
        text = f"{title}\n\nОбращений не найдено."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_feedbacks")]
        ])
    else:
        text = f"{title} ({len(feedbacks)})\n\n"

        # Показываем краткий список (без текста сообщения)
        for feedback in feedbacks[:15]:  # Максимум 15
            username = f"@{feedback.user.username}" if feedback.user.username else feedback.user.full_name
            text += (
                f"{feedback.status_emoji} <b>#{feedback.id}</b> | {username} | "
                f"{feedback.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            )

        if len(feedbacks) > 15:
            text += f"\n... и еще {len(feedbacks) - 15} обращений\n"

        text += "\nВыберите обращение:"

        # Кнопки обращений
        keyboard_buttons = []
        for feedback in feedbacks[:15]:
            username = f"@{feedback.user.username}" if feedback.user.username else f"ID{feedback.user.telegram_id}"
            button_text = f"{feedback.status_emoji} #{feedback.id} | {username}"
            keyboard_buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"feedback_view_{feedback.id}"
            )])

        keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_feedbacks")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("feedback_view_"))
@admin_required
async def view_feedback_details(callback: CallbackQuery, state: FSMContext):
    """Просмотр деталей обращения (для админа)"""
    await state.clear()

    feedback_id = int(callback.data.split("_")[2])
    feedback = await get_feedback_by_id(feedback_id)

    if not feedback:
        await callback.answer("❌ Обращение не найдено", show_alert=True)
        return

    username = f"@{feedback.user.username}" if feedback.user.username else feedback.user.full_name

    text = (
        f"💬 <b>Обращение #{feedback.id}</b>\n\n"
        f"От: {username} (ID: {feedback.user.telegram_id})\n"
        f"Статус: {feedback.status_emoji} {feedback.status_name}\n"
        f"Создано: {feedback.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Сообщение пользователя:</b>\n"
        f"{feedback.message_text}\n\n"
    )

    if feedback.admin_reply:
        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Ваш ответ:</b>\n"
            f"{feedback.admin_reply}\n\n"
            f"Дата ответа: {feedback.replied_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        )

    text += "━━━━━━━━━━━━━━━━━━━━"

    # Формируем кнопки в зависимости от статуса
    keyboard_buttons = []

    if feedback.status == "new":
        keyboard_buttons.append([InlineKeyboardButton(text="💬 Ответить", callback_data=f"feedback_reply_{feedback.id}")])
        keyboard_buttons.append([InlineKeyboardButton(text="🔒 Закрыть без ответа", callback_data=f"feedback_close_{feedback.id}")])
    elif feedback.status == "replied":
        keyboard_buttons.append([InlineKeyboardButton(text="✏️ Изменить ответ", callback_data=f"feedback_reply_{feedback.id}")])
        keyboard_buttons.append([InlineKeyboardButton(text="🔒 Закрыть обращение", callback_data=f"feedback_close_{feedback.id}")])
    elif feedback.status == "closed":
        keyboard_buttons.append([InlineKeyboardButton(text="📖 Просмотр (закрыто)", callback_data=f"feedback_view_{feedback.id}")])

    keyboard_buttons.append([InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"feedback_delete_{feedback.id}")])
    keyboard_buttons.append([InlineKeyboardButton(text="⬅️ К списку", callback_data="feedbacks_filter_all")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("feedback_reply_"))
@admin_required
async def start_reply(callback: CallbackQuery, state: FSMContext):
    """Начать ввод ответа на обращение"""
    feedback_id = int(callback.data.split("_")[2])
    feedback = await get_feedback_by_id(feedback_id)

    if not feedback:
        await callback.answer("❌ Обращение не найдено", show_alert=True)
        return

    await state.update_data(
        feedback_id=feedback_id,
        reply_message_id=callback.message.message_id,
        reply_chat_id=callback.message.chat.id
    )
    await state.set_state(FeedbackStates.entering_reply)

    text = (
        f"💬 <b>Ответ на обращение #{feedback.id}</b>\n\n"
        f"<b>Вопрос пользователя:</b>\n"
        f"{feedback.message_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    if feedback.admin_reply:
        text += (
            f"<b>Текущий ответ:</b>\n"
            f"{feedback.admin_reply}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )

    text += "Введите ваш ответ пользователю:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"feedback_view_{feedback_id}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(FeedbackStates.entering_reply)
async def save_reply(message: Message, state: FSMContext):
    """Сохранение ответа админа"""
    data = await state.get_data()
    feedback_id = data.get("feedback_id")
    message_id = data.get("reply_message_id")
    chat_id = data.get("reply_chat_id")

    reply_text = message.text.strip()

    if len(reply_text) < 5:
        await message.answer("❌ Ответ слишком короткий. Минимум 5 символов.")
        return

    if len(reply_text) > 2000:
        reply_text = reply_text[:2000]

    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except:
        pass

    try:
        # Сохраняем ответ
        feedback = await update_feedback_reply(feedback_id, reply_text)

        if not feedback:
            text = "❌ Обращение не найдено"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ К списку", callback_data="feedbacks_filter_all")]
            ])
        else:
            # Отправляем уведомление пользователю
            user_text = (
                f"✅ <b>Получен ответ от администратора!</b>\n\n"
                f"Ваше обращение #{feedback.id} от {feedback.created_at.strftime('%d.%m.%Y')}:\n"
                f"<i>{feedback.message_text[:100]}...</i>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>Ответ администратора:</b>\n"
                f"{reply_text}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )

            user_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Мои обращения", callback_data="my_feedbacks")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])

            try:
                await message.bot.send_message(
                    chat_id=feedback.user.telegram_id,
                    text=user_text,
                    reply_markup=user_keyboard
                )
            except Exception as e:
                logger.error(f"Не удалось отправить ответ пользователю: {e}")

            # Ответ админу
            text = (
                f"✅ <b>Ответ отправлен!</b>\n\n"
                f"Обращение #{feedback.id} — статус изменен на ✅ Отвечено\n"
                f"Пользователь получил уведомление."
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📖 Детали обращения", callback_data=f"feedback_view_{feedback_id}")],
                [InlineKeyboardButton(text="⬅️ К списку", callback_data="feedbacks_filter_all")]
            ])

        await message.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=keyboard
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка сохранения ответа: {e}")
        text = "❌ Ошибка при сохранении ответа"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К списку", callback_data="feedbacks_filter_all")]
        ])
        await message.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=keyboard
        )
        await state.clear()


@router.callback_query(F.data.startswith("feedback_close_") & ~F.data.startswith("feedback_close_confirm_"))
@admin_required
async def close_feedback_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение закрытия обращения"""
    await state.clear()

    feedback_id = int(callback.data.split("_")[2])
    feedback = await get_feedback_by_id(feedback_id)

    if not feedback:
        await callback.answer("❌ Обращение не найдено", show_alert=True)
        return

    text = (
        f"🔒 <b>Закрыть обращение #{feedback.id}?</b>\n\n"
        f"После закрытия обращение будет перемещено в архив.\n"
        f"Вы уверены?"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, закрыть", callback_data=f"feedback_close_confirm_{feedback_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"feedback_view_{feedback_id}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("feedback_close_confirm_"))
@admin_required
async def close_feedback_execute(callback: CallbackQuery, state: FSMContext):
    """Выполнение закрытия обращения"""
    await state.clear()

    feedback_id = int(callback.data.split("_")[3])
    feedback = await close_feedback(feedback_id)

    if not feedback:
        text = "❌ Ошибка при закрытии обращения"
    else:
        text = f"✅ Обращение #{feedback_id} закрыто"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К списку", callback_data="feedbacks_filter_all")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("feedback_delete_") & ~F.data.startswith("feedback_delete_confirm_"))
@admin_required
async def delete_feedback_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления обращения"""
    await state.clear()

    feedback_id = int(callback.data.split("_")[2])
    feedback = await get_feedback_by_id(feedback_id)

    if not feedback:
        await callback.answer("❌ Обращение не найдено", show_alert=True)
        return

    text = (
        f"🗑️ <b>Удалить обращение #{feedback.id}?</b>\n\n"
        f"Это действие необратимо!\n"
        f"Обращение будет удалено полностью."
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"feedback_delete_confirm_{feedback_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"feedback_view_{feedback_id}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("feedback_delete_confirm_"))
@admin_required
async def delete_feedback_execute(callback: CallbackQuery, state: FSMContext):
    """Выполнение удаления обращения"""
    await state.clear()

    feedback_id = int(callback.data.split("_")[3])
    success = await delete_feedback(feedback_id)

    if success:
        text = f"✅ Обращение #{feedback_id} удалено"
    else:
        text = "❌ Ошибка при удалении обращения"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К списку", callback_data="feedbacks_filter_all")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
