"""
Модель книг
"""
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.theme import Theme
    from bot.models.book_author import BookAuthor
    from bot.models.lesson import Lesson
    from bot.models.lesson_series import LessonSeries


class Book(Base):
    """Модель книги"""

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    theme_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("themes.id", ondelete="SET NULL"), nullable=True, index=True)
    author_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("book_authors.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    desc: Mapped[str] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now, onupdate=get_moscow_now)
    
    # Отношения
    theme: Mapped[Optional["Theme"]] = relationship(back_populates="books")
    author: Mapped[Optional["BookAuthor"]] = relationship(back_populates="books")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="book", cascade="all, delete-orphan")
    lesson_series: Mapped[list["LessonSeries"]] = relationship(back_populates="book")
    
    def __repr__(self) -> str:
        return f"<Book(id={self.id}, name='{self.name}')>"
    
    def __str__(self) -> str:
        return self.name
    
    @property
    def active_lessons_count(self) -> int:
        """Количество активных уроков в книге"""
        return len([lesson for lesson in self.lessons if lesson.is_active])
    
    @property
    def author_info(self) -> str:
        """Получение информации об авторе"""
        if self.author:
            return self.author.full_name_with_years
        return "Автор не указан"
    
    @property
    def display_name(self) -> str:
        """Отображаемое название книги с автором"""
        if self.author:
            return f"«{self.name}» - {self.author.name}"
        return f"«{self.name}»"