"""
Модель попыток прохождения теста
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.test import Test
    from bot.models.user import User


class TestAttempt(Base):
    """Модель попытки прохождения теста"""

    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Связи
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    test_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Временные метки
    started_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # NULL = не завершён

    # Результаты
    score: Mapped[int] = mapped_column(Integer, default=0)  # Набранные баллы
    max_score: Mapped[int] = mapped_column(Integer, nullable=False)  # Максимальные баллы
    passed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)  # Прошёл ли тест

    # Ответы пользователя (JSON)
    # Формат: {"question_1": 0, "question_2": 2, ...}  где значение = индекс выбранного ответа
    answers: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Время прохождения
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Отношения
    user: Mapped["User"] = relationship(back_populates="test_attempts")
    test: Mapped["Test"] = relationship(back_populates="attempts")

    def __repr__(self) -> str:
        return f"<TestAttempt(id={self.id}, user_id={self.user_id}, test_id={self.test_id}, score={self.score}/{self.max_score})>"

    @property
    def is_completed(self) -> bool:
        """Завершена ли попытка"""
        return self.completed_at is not None

    @property
    def score_percentage(self) -> float:
        """Процент правильных ответов"""
        if self.max_score == 0:
            return 0.0
        return round((self.score / self.max_score) * 100, 1)

    @property
    def formatted_time_spent(self) -> str:
        """Форматированное время прохождения"""
        if not self.time_spent_seconds:
            return "Неизвестно"

        minutes = self.time_spent_seconds // 60
        seconds = self.time_spent_seconds % 60

        if minutes > 0:
            return f"{minutes} мин {seconds} сек"
        return f"{seconds} сек"

    @property
    def result_summary(self) -> str:
        """Краткая сводка результатов"""
        status = "✅ Пройден" if self.passed else "❌ Не пройден"
        return f"{status}\n📊 Результат: {self.score}/{self.max_score} ({self.score_percentage}%)"

    @property
    def full_result(self) -> str:
        """Полная информация о результате"""
        info = f"{'✅ ТЕСТ ПРОЙДЕН' if self.passed else '❌ ТЕСТ НЕ ПРОЙДЕН'}\n\n"
        info += f"📊 Ваш результат: {self.score}/{self.max_score} баллов ({self.score_percentage}%)\n"
        info += f"✅ Для прохождения нужно: {self.test.passing_score}%\n"

        if self.time_spent_seconds:
            info += f"⏱ Время прохождения: {self.formatted_time_spent}\n"

        if not self.passed:
            info += f"\n💡 Попробуйте ещё раз! Количество попыток неограничено."

        return info
