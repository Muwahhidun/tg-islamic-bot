"""
Модель вопросов теста
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.test import Test
    from bot.models.lesson import Lesson


class TestQuestion(Base):
    """Модель вопроса теста"""

    __tablename__ = "test_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Урок, к которому относится вопрос (обязательное поле)
    lesson_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Текст вопроса
    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # 4 варианта ответа (сохраняем как JSON список)
    # Пример: ["Ответ 1", "Ответ 2", "Ответ 3", "Ответ 4"]
    options: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Индекс правильного ответа (0-3)
    correct_answer_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Объяснение (не показываем пользователю, только для админа)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Порядок вопроса в тесте
    order: Mapped[int] = mapped_column(Integer, default=0, index=True)

    # Баллы за вопрос (всегда 1)
    points: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now, onupdate=get_moscow_now)

    # Отношения
    test: Mapped["Test"] = relationship(back_populates="questions")
    lesson: Mapped["Lesson"] = relationship()

    def __repr__(self) -> str:
        return f"<TestQuestion(id={self.id}, test_id={self.test_id})>"

    def __str__(self) -> str:
        return self.question_text[:50] + "..." if len(self.question_text) > 50 else self.question_text

    @property
    def options_list(self) -> list[str]:
        """Получение списка вариантов ответа"""
        if isinstance(self.options, list):
            return self.options
        return []

    @property
    def correct_answer(self) -> str:
        """Получение правильного ответа"""
        options = self.options_list
        if 0 <= self.correct_answer_index < len(options):
            return options[self.correct_answer_index]
        return ""

    def is_correct(self, answer_index: int) -> bool:
        """Проверка правильности ответа"""
        return answer_index == self.correct_answer_index

    @property
    def display_question(self) -> str:
        """Форматированный вопрос с вариантами ответа"""
        text = f"❓ {self.question_text}\n\n"

        for i, option in enumerate(self.options_list, 1):
            text += f"{i}. {option}\n"

        return text
