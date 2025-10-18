"""
Декораторы для бота
"""
from functools import wraps
import inspect
from typing import Callable, Union, Any

from aiogram import types
from aiogram.fsm.context import FSMContext

from bot.services.database_service import get_user_by_telegram_id, get_user_with_role
from bot.utils.config import config


def admin_required(func: Callable) -> Callable:
    """
    Декоратор для проверки прав администратора
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Определяем, где находится объект сообщения или колбэка
        message = None
        callback = None
        
        for arg in args:
            if isinstance(arg, types.Message):
                message = arg
            elif isinstance(arg, types.CallbackQuery):
                callback = arg
        
        # Если это колбэк, получаем из него сообщение
        if callback and not message:
            message = callback.message
        
        if not message:
            # Если нет сообщения, просто вызываем функцию
            return await func(*args, **kwargs)
        
        # Проверяем, является ли пользователь администратором
        user_id = message.from_user.id
        admin_id = int(config.admin_telegram_id)  # Убедимся, что оба значения целые числа
        
        # Добавляем логирование для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Admin check - User ID: {user_id} (type: {type(user_id)}), Config admin ID: {admin_id} (type: {type(admin_id)}), Match: {user_id == admin_id}")
        
        # Проверяем по ID администратора из конфига
        if user_id == admin_id:
            logger.info(f"Access granted by config admin ID")
            return await func(*args, **kwargs)
        
        # Проверяем по роли в базе данных
        user = await get_user_with_role(user_id)
        
        # Добавляем логирование для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Admin check - User ID: {user_id}, User: {user}, Role: {user.role if user else None}, Role name: {user.role.name if user and user.role else None}")
        
        if user and user.role and user.role.name in ["admin", "moderator"]:
            return await func(*args, **kwargs)
        
        # Если пользователь не администратор, отправляем сообщение об отказе
        await message.answer(
            "❌ <b>Доступ запрещен</b>\n\n"
            "Эта команда доступна только администраторам.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        # Если это колбэк, отвечаем на него
        if callback:
            await callback.answer()
        
        return None
    
    return wrapper


def moderator_required(func: Callable) -> Callable:
    """
    Декоратор для проверки прав модератора
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Определяем, где находится объект сообщения или колбэка
        message = None
        callback = None
        
        for arg in args:
            if isinstance(arg, types.Message):
                message = arg
            elif isinstance(arg, types.CallbackQuery):
                callback = arg
        
        # Если это колбэк, получаем из него сообщение
        if callback and not message:
            message = callback.message
        
        if not message:
            # Если нет сообщения, просто вызываем функцию
            return await func(*args, **kwargs)
        
        # Проверяем, является ли пользователь модератором или администратором
        user_id = message.from_user.id
        
        # Проверяем по ID администратора из конфига
        if user_id == config.admin_telegram_id:
            return await func(*args, **kwargs)
        
        # Проверяем по роли в базе данных
        user = await get_user_with_role(user_id)
        if user and user.role and user.role.name in ["admin", "moderator"]:
            return await func(*args, **kwargs)
        
        # Если пользователь не модератор, отправляем сообщение об отказе
        await message.answer(
            "❌ <b>Доступ запрещен</b>\n\n"
            "Эта команда доступна только модераторам и администраторам.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        
        # Если это колбэк, отвечаем на него
        if callback:
            await callback.answer()
        
        return None
    
    return wrapper


def clear_state(func: Callable) -> Callable:
    """
    Декоратор для очистки состояния FSM после выполнения функции
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Ищем объект FSMContext в аргументах
        state = None
        for arg in args:
            if isinstance(arg, FSMContext):
                state = arg
                break
        
        try:
            # Выполняем основную функцию
            result = await func(*args, **kwargs)
            return result
        finally:
            # Очищаем состояние, если оно было найдено
            if state:
                await state.clear()
    
    return wrapper


def error_handler(func: Callable) -> Callable:
    """
    Декоратор для обработки ошибок
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Определяем, где находится объект сообщения или колбэка
        message = None
        callback = None
        
        for arg in args:
            if isinstance(arg, types.Message):
                message = arg
            elif isinstance(arg, types.CallbackQuery):
                callback = arg
        
        # Если это колбэк, получаем из него сообщение
        if callback and not message:
            message = callback.message
        
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Логируем ошибку
            import logging
            logging.error(f"Ошибка в функции {func.__name__}: {e}")
            
            # Отправляем сообщение об ошибке пользователю
            if message:
                await message.answer(
                    "❌ <b>Произошла ошибка</b>\n\n"
                    "Попробуйте повторить действие позже. "
                    "Если проблема сохранится, обратитесь к администратору."
                )
            
            # Если это колбэк, отвечаем на него
            if callback:
                await callback.answer(
                    "Произошла ошибка",
                    show_alert=True
                )
            
            return None
    
    return wrapper


def user_required(func: Callable) -> Callable:
    """
    Декоратор для проверки регистрации пользователя
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Определяем, где находится объект сообщения или колбэка
        message = None
        callback = None
        
        for arg in args:
            if isinstance(arg, types.Message):
                message = arg
            elif isinstance(arg, types.CallbackQuery):
                callback = arg
        
        # Если это колбэк, получаем из него сообщение
        if callback and not message:
            message = callback.message
        
        if not message:
            # Если нет сообщения, просто вызываем функцию
            return await func(*args, **kwargs)
        
        # Проверяем, зарегистрирован ли пользователь
        user_id = message.from_user.id
        user = await get_user_by_telegram_id(user_id)
        
        if not user:
            # Если пользователь не найден, регистрируем его
            from bot.services.database_service import UserService
            user = await UserService.get_or_create_user(
                telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name
            )
        
        # Добавляем пользователя в kwargs только если функция его ожидает
        if 'user' in inspect.signature(func).parameters:
            kwargs['user'] = user
        
        return await func(*args, **kwargs)
    
    return wrapper


def user_required_callback(func: Callable) -> Callable:
    """
    Декоратор для проверки регистрации пользователя в колбэках
    """
    @wraps(func)
    async def wrapper(callback: types.CallbackQuery, *args, **kwargs) -> Any:
        # Проверяем, зарегистрирован ли пользователь
        user_id = callback.from_user.id
        user = await get_user_by_telegram_id(user_id)
        
        if not user:
            # Если пользователь не найден, регистрируем его
            from bot.services.database_service import UserService
            user = await UserService.get_or_create_user(
                telegram_id=user_id,
                username=callback.from_user.username,
                first_name=callback.from_user.first_name,
                last_name=callback.from_user.last_name
            )
        
        # Добавляем пользователя в kwargs только если функция его ожидает
        if 'user' in inspect.signature(func).parameters:
            kwargs['user'] = user
        
        return await func(callback, *args, **kwargs)
    
    return wrapper