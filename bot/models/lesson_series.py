"""
Модель серии уроков (lesson_series)
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.book import Book
    from bot.models.lesson import Lesson
    from bot.models.lesson_teacher import LessonTeacher
    from bot.models.test import Test
    from bot.models.theme import Theme


class LessonSeries(Base):
    """Модель серии/цикла уроков"""

    __tablename__ = "lesson_series"
    __table_args__ = (
        UniqueConstraint('year', 'name', 'teacher_id', name='unique_series_per_teacher'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Обязательный преподаватель
    teacher_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("lesson_teachers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )

    # Опциональные связи
    book_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("books.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    theme_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("themes.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Метаданные серии
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    order: Mapped[int] = mapped_column(Integer, default=0)  # Для сортировки
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now, onupdate=get_moscow_now)

    # Отношения
    teacher: Mapped["LessonTeacher"] = relationship(back_populates="lesson_series")
    book: Mapped["Book | None"] = relationship(back_populates="lesson_series")
    theme: Mapped["Theme | None"] = relationship(back_populates="lesson_series")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="series",
        cascade="save-update, merge",  # Не удаляем уроки при удалении серии
        foreign_keys="[Lesson.series_id]"
    )
    tests: Mapped[list["Test"]] = relationship(back_populates="series", foreign_keys="[Test.series_id]")

    def __repr__(self) -> str:
        return f"<LessonSeries(id={self.id}, name='{self.name}', year={self.year})>"

    def __str__(self) -> str:
        return f"{self.year} - {self.name}"

    @property
    def display_name(self) -> str:
        """Отображаемое название серии"""
        return f"{self.year} - {self.name}"

    @property
    def teacher_name(self) -> str:
        """Получение имени преподавателя"""
        return self.teacher.name if self.teacher else "Преподаватель не указан"

    @property
    def book_title(self) -> str | None:
        """Получение названия книги"""
        return self.book.name if self.book else None

    @property
    def theme_name(self) -> str | None:
        """Получение названия темы (приоритет: тема книги > прямая тема серии)"""
        # Сначала проверяем тему книги
        try:
            if self.book and self.book.theme:
                return self.book.theme.name
        except Exception:
            pass  # Session закрыта

        # Если у книги нет темы, берем прямую тему серии
        try:
            if self.theme:
                return self.theme.name
        except Exception:
            pass

        return None

    @property
    def total_lessons(self) -> int:
        """Количество уроков в серии"""
        return len(self.lessons) if self.lessons else 0

    @property
    def active_lessons_count(self) -> int:
        """Количество активных уроков"""
        return len([l for l in self.lessons if l.is_active]) if self.lessons else 0

    @property
    def total_duration_seconds(self) -> int:
        """Общая длительность всех уроков в секундах"""
        if not self.lessons:
            return 0
        return sum(lesson.duration_seconds or 0 for lesson in self.lessons)

    @property
    def formatted_total_duration(self) -> str:
        """Форматированная общая длительность"""
        total = self.total_duration_seconds
        if not total:
            return "Длительность неизвестна"

        hours = total // 3600
        minutes = (total % 3600) // 60
        seconds = total % 60

        if hours > 0:
            return f"{hours}ч {minutes}м"
        elif minutes > 0:
            return f"{minutes}м {seconds}с"
        else:
            return f"{seconds}с"

    @property
    def full_info(self) -> str:
        """Полная информация о серии для отображения"""
        info = f"📚 {self.display_name}\n"
        info += f"👤 {self.teacher_name}\n"

        if self.book_title:
            info += f"📖 Книга: {self.book_title}\n"

        if self.theme_name:
            info += f"📑 Тема: {self.theme_name}\n"

        info += f"🎧 Уроков: {self.active_lessons_count}/{self.total_lessons}\n"

        if self.total_duration_seconds > 0:
            info += f"⏱ Длительность: {self.formatted_total_duration}\n"

        if self.is_completed:
            info += "✅ Серия завершена\n"
        else:
            info += "🔄 В процессе\n"

        if self.description:
            info += f"\n📝 {self.description}"

        return info
