"""
Обработчики управления тестами для администраторов
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.decorators import admin_required

router = Router()


@router.callback_query(F.data == "admin_tests")
@admin_required
async def tests_menu(callback: CallbackQuery):
    """Главное меню управления тестами"""
    text = (
        "📝 <b>Управление тестами</b>\n\n"
        "Раздел в разработке.\n\n"
        "Здесь будет возможность:\n"
        "• Создавать тесты для уроков\n"
        "• Создавать тесты для серий\n"
        "• Редактировать вопросы\n"
        "• Просматривать результаты пользователей"
    )

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_panel"))
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
