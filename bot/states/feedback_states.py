from aiogram.fsm.state import State, StatesGroup


class FeedbackStates(StatesGroup):
    """Состояния для обратной связи"""

    # Пользователь вводит сообщение
    entering_message = State()

    # Админ вводит ответ
    entering_reply = State()
