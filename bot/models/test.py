"""
Модель тестов
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from enum import Enum

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.lesson import Lesson
    from bot.models.lesson_series import LessonSeries
    from bot.models.lesson_teacher import LessonTeacher
    from bot.models.test_question import TestQuestion
    from bot.models.test_attempt import TestAttempt


class TestType(str, Enum):
    """Тип теста"""
    LESSON = "lesson"  # Тест по уроку
    SERIES = "series"  # Тест по всей серии


class Test(Base):
    """Модель теста"""

    __tablename__ = "tests"
    __table_args__ = (
        CheckConstraint(
            "(test_type = 'lesson' AND lesson_id IS NOT NULL AND series_id IS NULL) OR "
            "(test_type = 'series' AND series_id IS NOT NULL AND lesson_id IS NULL)",
            name="check_test_type_consistency"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Тип теста
    test_type: Mapped[TestType] = mapped_column(
        SQLEnum(TestType, native_enum=False, length=50),
        nullable=False,
        index=True
    )

    # Связи с уроком или серией (одно из двух обязательно)
    lesson_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    series_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("lesson_series.id", ondelete="CASCADE"),
        nullable=True,
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
    passing_score: Mapped[int] = mapped_column(Integer, default=70)  # Процент для прохождения (70%)
    time_per_question_seconds: Mapped[int] = mapped_column(Integer, default=30)  # 30 секунд на вопрос
    questions_count: Mapped[int] = mapped_column(Integer, default=0)  # Автоматически считается

    # Метаданные
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    order: Mapped[int] = mapped_column(Integer, default=0)  # Порядок прохождения
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now, onupdate=get_moscow_now)

    # Отношения
    lesson: Mapped["Lesson | None"] = relationship(back_populates="tests", foreign_keys=[lesson_id])
    series: Mapped["LessonSeries | None"] = relationship(back_populates="tests", foreign_keys=[series_id])
    teacher: Mapped["LessonTeacher"] = relationship(back_populates="tests")
    questions: Mapped[list["TestQuestion"]] = relationship(
        back_populates="test",
        cascade="all, delete-orphan",
        order_by="TestQuestion.order"
    )
    attempts: Mapped[list["TestAttempt"]] = relationship(back_populates="test", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Test(id={self.id}, title='{self.title}', type={self.test_type})>"

    def __str__(self) -> str:
        return self.title

    @property
    def display_title(self) -> str:
        """Отображаемое название теста"""
        if self.test_type == TestType.LESSON and self.lesson:
            return f"Тест: {self.lesson.title}"
        elif self.test_type == TestType.SERIES and self.series:
            return f"Итоговый тест: {self.series.display_name}"
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

        if self.test_type == TestType.SERIES:
            info += f"\n⚠️ Доступен после прохождения всех тестов по урокам серии"

        return info
