from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.states.feedback_states import FeedbackStates
from bot.services.database_service import (
    create_feedback,
    get_feedbacks_by_user,
    get_user_by_telegram_id
)
from bot.utils.decorators import user_required_callback, user_required
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "feedback")
@user_required_callback
async def feedback_menu(callback: CallbackQuery, state: FSMContext, user):
    """Меню обратной связи"""
    await state.clear()

    text = (
        "💬 <b>Обратная связь</b>\n\n"
        "Напишите ваше сообщение администратору:\n\n"
        "• Сообщить об ошибке\n"
        "• Предложить улучшение\n"
        "• Задать вопрос\n"
        "• Добавить контент\n\n"
        "Администратор ответит в ближайшее время."
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Написать сообщение", callback_data="feedback_write")],
        [InlineKeyboardButton(text="📋 Мои обращения", callback_data="my_feedbacks")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "feedback_write")
@user_required_callback
async def start_feedback_write(callback: CallbackQuery, state: FSMContext, user):
    """Начать ввод сообщения"""
    # Сохраняем координаты сообщения для паттерна одного окна
    await state.update_data(
        feedback_message_id=callback.message.message_id,
        feedback_chat_id=callback.message.chat.id
    )

    text = (
        "✍️ <b>Введите ваше сообщение</b>\n\n"
        "Напишите текст обращения к администратору\n"
        "(минимум 10 символов)"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="feedback")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(FeedbackStates.entering_message)
    await callback.answer()


@router.message(FeedbackStates.entering_message)
@user_required
async def save_feedback(message: Message, state: FSMContext, user):
    """Сохранение сообщения обратной связи"""
    data = await state.get_data()
    message_id = data.get("feedback_message_id")
    chat_id = data.get("feedback_chat_id")

    message_text = message.text.strip()

    # Удаляем сообщение пользователя (паттерн одного окна)
    try:
        await message.delete()
    except:
        pass

    # Проверка длины
    if len(message_text) < 10:
        text = "❌ Сообщение слишком короткое. Минимум 10 символов.\n\nПопробуйте ещё раз:"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="feedback")]
        ])
        await message.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=keyboard
        )
        return

    if len(message_text) > 2000:
        message_text = message_text[:2000]

    # Создаем обращение
    try:
        feedback = await create_feedback(
            user_id=user.id,
            message_text=message_text
        )

        # Уведомление администратору
        import os
        admin_telegram_id = int(os.getenv("ADMIN_TELEGRAM_ID"))

        admin_text = (
            f"🆕 <b>Новое обращение #{feedback.id}</b>\n\n"
            f"От: {user.username or user.full_name} (ID: {user.telegram_id})\n"
            f"Дата: {feedback.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{message_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )

        admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Ответить", callback_data=f"feedback_reply_{feedback.id}")],
            [InlineKeyboardButton(text="📨 Все обращения", callback_data="admin_feedbacks")]
        ])

        try:
            await message.bot.send_message(
                chat_id=admin_telegram_id,
                text=admin_text,
                reply_markup=admin_keyboard
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу: {e}")

        # Ответ пользователю (паттерн одного окна)
        text = (
            "✅ <b>Сообщение отправлено!</b>\n\n"
            f"Номер обращения: #{feedback.id}\n"
            f"Дата: {feedback.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
            "Администратор ответит в ближайшее время.\n"
            "Вы получите уведомление."
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои обращения", callback_data="my_feedbacks")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])

        await message.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=keyboard
        )
        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка создания обращения: {e}")
        text = "❌ Ошибка при отправке сообщения. Попробуйте позже."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        await message.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=keyboard
        )
        await state.clear()


@router.callback_query(F.data == "my_feedbacks")
@user_required_callback
async def show_my_feedbacks(callback: CallbackQuery, state: FSMContext, user):
    """Показать обращения пользователя"""
    await state.clear()

    feedbacks = await get_feedbacks_by_user(user.id)

    if not feedbacks:
        text = (
            "📋 <b>Мои обращения</b>\n\n"
            "У вас пока нет обращений."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Написать администратору", callback_data="feedback_write")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="feedback")]
        ])
    else:
        text = f"📋 <b>Мои обращения ({len(feedbacks)})</b>\n\n"

        # Группируем по статусам
        new_feedbacks = [f for f in feedbacks if f.status == "new"]
        replied_feedbacks = [f for f in feedbacks if f.status == "replied"]
        closed_feedbacks = [f for f in feedbacks if f.status == "closed"]

        if new_feedbacks:
            text += f"🆕 <b>Новые ({len(new_feedbacks)}):</b>\n"
            for feedback in new_feedbacks[:5]:
                short_text = feedback.message_text[:50] + "..." if len(feedback.message_text) > 50 else feedback.message_text
                text += f"• #{feedback.id} | {feedback.created_at.strftime('%d.%m.%Y')}\n"
            text += "\n"

        if replied_feedbacks:
            text += f"✅ <b>Отвечено ({len(replied_feedbacks)}):</b>\n"
            for feedback in replied_feedbacks[:5]:
                text += f"• #{feedback.id} | {feedback.created_at.strftime('%d.%m.%Y')}\n"
            text += "\n"

        if closed_feedbacks:
            text += f"🔒 <b>Закрыто ({len(closed_feedbacks)}):</b>\n"
            for feedback in closed_feedbacks[:3]:
                text += f"• #{feedback.id} | {feedback.created_at.strftime('%d.%m.%Y')}\n"
            text += "\n"

        text += "Выберите обращение:"

        # Кнопки обращений
        keyboard_buttons = []
        for feedback in feedbacks[:10]:  # Показываем максимум 10
            button_text = f"{feedback.status_emoji} #{feedback.id} | {feedback.created_at.strftime('%d.%m')}"
            keyboard_buttons.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"view_feedback_{feedback.id}"
            )])

        keyboard_buttons.append([InlineKeyboardButton(text="💬 Новое обращение", callback_data="feedback_write")])
        keyboard_buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="feedback")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("view_feedback_"))
@user_required_callback
async def view_feedback(callback: CallbackQuery, state: FSMContext, user):
    """Просмотр деталей обращения"""
    await state.clear()

    feedback_id = int(callback.data.split("_")[2])

    from bot.services.database_service import get_feedback_by_id
    feedback = await get_feedback_by_id(feedback_id)

    if not feedback or feedback.user_id != user.id:
        await callback.answer("❌ Обращение не найдено", show_alert=True)
        return

    text = (
        f"💬 <b>Обращение #{feedback.id}</b>\n\n"
        f"Статус: {feedback.status_emoji} {feedback.status_name}\n"
        f"Дата: {feedback.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Ваше сообщение:</b>\n"
        f"{feedback.message_text}\n\n"
    )

    if feedback.admin_reply:
        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Ответ администратора:</b>\n"
            f"{feedback.admin_reply}\n\n"
            f"Дата ответа: {feedback.replied_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        )

    text += "━━━━━━━━━━━━━━━━━━━━"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ К обращениям", callback_data="my_feedbacks")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
