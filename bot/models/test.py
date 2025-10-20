"""
Модель тестов
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.lesson_series import LessonSeries
    from bot.models.lesson_teacher import LessonTeacher
    from bot.models.test_question import TestQuestion
    from bot.models.test_attempt import TestAttempt


class Test(Base):
    """Модель теста"""

    __tablename__ = "tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Связь с серией (обязательно - один тест на серию)
    series_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lesson_series.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Создатель теста (преподаватель)
    teacher_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lesson_teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Настройки теста
    passing_score: Mapped[int] = mapped_column(Integer, default=80)  # Процент для прохождения (80%)
    time_per_question_seconds: Mapped[int] = mapped_column(Integer, default=30)  # 30 секунд на вопрос
    questions_count: Mapped[int] = mapped_column(Integer, default=0)  # Автоматически считается

    # Метаданные
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    order: Mapped[int] = mapped_column(Integer, default=0)  # Порядок прохождения
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now, onupdate=get_moscow_now)

    # Отношения
    series: Mapped["LessonSeries"] = relationship(back_populates="tests")
    teacher: Mapped["LessonTeacher"] = relationship(back_populates="tests")
    questions: Mapped[list["TestQuestion"]] = relationship(
        back_populates="test",
        cascade="all, delete-orphan",
        order_by="TestQuestion.order"
    )
    attempts: Mapped[list["TestAttempt"]] = relationship(back_populates="test", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Test(id={self.id}, title='{self.title}', series_id={self.series_id})>"

    def __str__(self) -> str:
        return self.title

    @property
    def display_title(self) -> str:
        """Отображаемое название теста"""
        if self.series:
            return f"{self.title} ({self.series.display_name})"
        return self.title

    @property
    def total_time_seconds(self) -> int:
        """Общее время на тест"""
        return self.questions_count * self.time_per_question_seconds

    @property
    def formatted_time(self) -> str:
        """Форматированное время теста"""
        total = self.total_time_seconds
        minutes = total // 60
        seconds = total % 60

        if minutes > 0:
            return f"{minutes} мин {seconds} сек"
        return f"{seconds} сек"

    @property
    def max_score(self) -> int:
        """Максимальный балл (каждый вопрос = 1 балл)"""
        return self.questions_count

    @property
    def passing_points(self) -> int:
        """Количество баллов для прохождения"""
        return int(self.max_score * self.passing_score / 100)

    @property
    def attempts_count(self) -> int:
        """Количество попыток прохождения"""
        return len(self.attempts) if self.attempts else 0

    @property
    def passed_count(self) -> int:
        """Количество успешных прохождений"""
        return len([a for a in self.attempts if a.passed]) if self.attempts else 0

    @property
    def full_info(self) -> str:
        """Полная информация о тесте"""
        info = f"📝 {self.display_title}\n\n"

        if self.description:
            info += f"{self.description}\n\n"

        info += f"❓ Вопросов: {self.questions_count}\n"
        info += f"⏱ Время: {self.formatted_time} ({self.time_per_question_seconds} сек/вопрос)\n"
        info += f"✅ Для прохождения: {self.passing_score}% ({self.passing_points}/{self.max_score} баллов)\n"
        info += f"🔄 Попыток: неограниченно (засчитывается лучшая)\n"

        return info
