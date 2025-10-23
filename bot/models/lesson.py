"""
Модель уроков
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.book import Book
    from bot.models.lesson_series import LessonSeries
    from bot.models.lesson_teacher import LessonTeacher
    from bot.models.test import Test
    from bot.models.theme import Theme


class Lesson(Base):
    """Модель урока"""

    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint('series_id', 'lesson_number', name='unique_lesson_number_per_series'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Связь с серией (новое поле)
    series_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("lesson_series.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Поля наследуются от series, но могут быть переопределены
    book_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("books.id", ondelete="SET NULL"), nullable=True, index=True)
    teacher_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("lesson_teachers.id", ondelete="SET NULL"), nullable=True, index=True)
    theme_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("themes.id", ondelete="SET NULL"), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str] = mapped_column(String(500), nullable=True)
    telegram_file_id: Mapped[str | None] = mapped_column(String(200), nullable=True)  # Кеш file_id для быстрой отправки
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    tags: Mapped[str] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now, onupdate=get_moscow_now)
    
    # Отношения
    series: Mapped["LessonSeries | None"] = relationship(back_populates="lessons", foreign_keys=[series_id])
    book: Mapped["Book | None"] = relationship(back_populates="lessons")
    teacher: Mapped["LessonTeacher | None"] = relationship(back_populates="lessons")
    theme: Mapped["Theme | None"] = relationship("Theme", foreign_keys=[theme_id])
    
    def __repr__(self) -> str:
        return f"<Lesson(id={self.id}, title='{self.title}')>"
    
    def __str__(self) -> str:
        return self.title

    # Валидатор theme_id убран - теперь theme_id хранится для производительности
    # даже если есть book_id (денормализация для быстрых запросов)

    @property
    def formatted_duration(self) -> str:
        """Форматированная длительность урока"""
        if not self.duration_seconds:
            return "Длительность неизвестна"
        
        hours = self.duration_seconds // 3600
        minutes = (self.duration_seconds % 3600) // 60
        seconds = self.duration_seconds % 60
        
        if hours > 0:
            return f"{hours}ч {minutes}м {seconds}с"
        elif minutes > 0:
            return f"{minutes}м {seconds}с"
        else:
            return f"{seconds}с"
    
    @property
    def display_title(self) -> str:
        """Отображаемое название урока с номером"""
        if self.lesson_number:
            return f"Урок {self.lesson_number}"
        return "Без номера"
    
    @property
    def tags_list(self) -> list[str]:
        """Получение списка тегов"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]
    
    @tags_list.setter
    def tags_list(self, tags: list[str]):
        """Установка списка тегов"""
        self.tags = ", ".join(tags) if tags else None
    
    @property
    def teacher_name(self) -> str:
        """Получение имени преподавателя"""
        return self.teacher.name if self.teacher else "Преподаватель не указан"
    
    @property
    def book_title(self) -> str:
        """Получение названия книги"""
        return self.book.name if self.book else "Книга не указана"
    
    @property
    def effective_theme_id(self) -> Optional[int]:
        """Получение эффективного ID темы (приоритет у книги)"""
        if self.book and self.book.theme:
            return self.book.theme.id
        return self.theme_id

    @property
    def effective_theme(self) -> Optional["Theme"]:
        """Получение эффективной темы (приоритет у книги)"""
        if self.book and self.book.theme:
            return self.book.theme
        return self.theme

    @property
    def theme_name(self) -> str:
        """Получение названия темы"""
        effective_theme = self.effective_theme
        if effective_theme:
            return effective_theme.name
        return "Тема не указана"

    @property
    def series_display(self) -> str:
        """Отображение серии"""
        if self.series_id:
            try:
                if self.series:
                    return self.series.display_name
            except Exception:
                pass  # Session закрыта
        return "Серия не указана"

    @property
    def full_display_title(self) -> str:
        """Полное отображаемое название с серией"""
        lesson_part = f"Урок {self.lesson_number}" if self.lesson_number else "Без номера"
        return f"{self.series_display} | {lesson_part}"

    def has_audio(self) -> bool:
        """Проверка наличия аудиофайла"""
        return bool(self.audio_path)