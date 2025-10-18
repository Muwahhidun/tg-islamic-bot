"""
Модель уроков
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base

if TYPE_CHECKING:
    from bot.models.book import Book
    from bot.models.lesson_teacher import LessonTeacher


class Lesson(Base):
    """Модель урока"""
    
    __tablename__ = "lessons"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id", ondelete="CASCADE"), index=True)
    teacher_id: Mapped[int] = mapped_column(Integer, ForeignKey("lesson_teachers.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str] = mapped_column(String(500), nullable=True)
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=True)
    tags: Mapped[str] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    book: Mapped["Book"] = relationship(back_populates="lessons")
    teacher: Mapped["LessonTeacher"] = relationship(back_populates="lessons")
    
    def __repr__(self) -> str:
        return f"<Lesson(id={self.id}, title='{self.title}')>"
    
    def __str__(self) -> str:
        return self.title
    
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
            return f"Урок {self.lesson_number}: {self.title}"
        return self.title
    
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
    def theme_name(self) -> str:
        """Получение названия темы"""
        if self.book and self.book.theme:
            return self.book.theme.name
        return "Тема не указана"
    
    def has_audio(self) -> bool:
        """Проверка наличия аудиофайла"""
        return bool(self.audio_path)