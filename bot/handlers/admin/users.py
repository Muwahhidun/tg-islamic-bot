"""
User management handlers for admin panel
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.orm import joinedload

from bot.utils.decorators import admin_required
from bot.services.database_service import UserService, RoleService

router = Router()


class UserStates(StatesGroup):
    """States for user management"""
    role = State()


@router.callback_query(F.data == "admin_users")
@admin_required
async def admin_users(callback: CallbackQuery):
    """Show list of users for management"""
    # Get all users
    users = await UserService.get_all_users(limit=50)

    builder = InlineKeyboardBuilder()

    if not users:
        builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
        await callback.message.edit_text(
            "👥 <b>Управление пользователями</b>\n\n"
            "Пользователи не найдены",
            reply_markup=builder.as_markup()
        )
        await callback.answer()
        return

    # Group users by roles
    admins = []
    moderators = []
    regular_users = []

    for user in users:
        if user.role and user.role.name == "admin":
            admins.append(user)
        elif user.role and user.role.name == "moderator":
            moderators.append(user)
        else:
            regular_users.append(user)

    text = "👥 <b>Управление пользователями</b>\n\n"

    if admins:
        text += f"🔹 <b>Администраторы ({len(admins)})</b>\n"
        for user in admins[:5]:  # Show only first 5
            status = "✅" if user.is_active else "❌"
            text += f"{status} {user.first_name or 'Без имени'} (@{user.username or 'no_username'}) - ID: {user.telegram_id}\n"
        if len(admins) > 5:
            text += f"... и еще {len(admins) - 5}\n"
        text += "\n"

    if moderators:
        text += f"🔹 <b>Модераторы ({len(moderators)})</b>\n"
        for user in moderators[:5]:  # Show only first 5
            status = "✅" if user.is_active else "❌"
            text += f"{status} {user.first_name or 'Без имени'} (@{user.username or 'no_username'}) - ID: {user.telegram_id}\n"
        if len(moderators) > 5:
            text += f"... и еще {len(moderators) - 5}\n"
        text += "\n"

    if regular_users:
        text += f"🔹 <b>Пользователи ({len(regular_users)})</b>\n"
        for user in regular_users[:5]:  # Show only first 5
            status = "✅" if user.is_active else "❌"
            text += f"{status} {user.first_name or 'Без имени'} (@{user.username or 'no_username'}) - ID: {user.telegram_id}\n"
        if len(regular_users) > 5:
            text += f"... и еще {len(regular_users) - 5}\n"

    builder.add(InlineKeyboardButton(text="➕ Добавить/изменить роль пользователя", callback_data="add_user_role"))
    builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "add_user_role")
@admin_required
async def add_user_role_start(callback: CallbackQuery, state: FSMContext):
    """Start the process of adding/changing user role"""
    await callback.message.edit_text(
        "👥 <b>Управление ролями пользователей</b>\n\n"
        "Введите Telegram ID пользователя, которому хотите назначить или изменить роль:\n\n"
        "<i>Чтобы узнать ID пользователя, попросите его отправить команду /id или воспользуйтесь ботами вроде @userinfobot</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_users")]])
    )
    await state.set_state(UserStates.role)
    await callback.answer()


@router.message(UserStates.role)
@admin_required
async def process_user_id(message: Message, state: FSMContext):
    """Process user ID"""
    try:
        telegram_id = int(message.text)
        user = await UserService.get_user_by_telegram_id(telegram_id)

        if not user:
            # If user is not in database, create them
            user = await UserService.create_user(
                telegram_id=telegram_id,
                username=None,  # Will be updated on first bot interaction
                first_name=None,
                last_name=None,
                role_id=3  # Default user role
            )

        # Get all roles
        roles = await RoleService.get_all_roles()

        builder = InlineKeyboardBuilder()
        for role in roles:
            builder.add(InlineKeyboardButton(
                text=f"{role.name} ({role.description})",
                callback_data=f"set_role_{user.id}_{role.id}"
            ))

        builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users"))
        builder.adjust(1)

        current_role = user.role.name if user.role else "не назначена"

        await message.answer(
            f"👤 <b>Пользователь найден</b>\n\n"
            f"ID: {user.telegram_id}\n"
            f"Имя: {user.first_name or 'Не указано'}\n"
            f"Username: @{user.username or 'не указан'}\n"
            f"Текущая роль: {current_role}\n\n"
            f"Выберите новую роль:",
            reply_markup=builder.as_markup()
        )
        await state.clear()

    except ValueError:
        await message.answer(
            "❌ Неверный формат ID. Введите числовой ID пользователя:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_users")]])
        )


@router.callback_query(F.data.startswith("set_role_"))
@admin_required
async def set_user_role(callback: CallbackQuery):
    """Set user role"""
    parts = callback.data.split("_")
    user_id = int(parts[2])  # This is internal DB ID
    role_id = int(parts[3])

    # Get user by internal DB ID and role
    user = await UserService.get_user_by_id(user_id)
    role = await RoleService.get_role_by_id(role_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    if not role:
        await callback.answer("❌ Роль не найдена", show_alert=True)
        return

    # Update user role by internal DB ID
    await UserService.update_user_role_by_id(user_id, role_id)

    await callback.answer(f"✅ Роль '{role.name}' назначена пользователю", show_alert=True)

    # Redirect to users list
    await admin_users(callback)
