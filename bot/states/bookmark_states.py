"""
FSM состояния для работы с закладками
"""
from aiogram.fsm.state import State, StatesGroup


class BookmarkStates(StatesGroup):
    """Состояния для управления закладками"""
    entering_name = State()  # Ввод названия закладки при добавлении
    renaming = State()  # Переименование существующей закладки
