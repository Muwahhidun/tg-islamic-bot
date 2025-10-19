"""
Модель преподавателей уроков
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.lesson import Lesson
    from bot.models.lesson_series import LessonSeries
    from bot.models.test import Test


class LessonTeacher(Base):
    """Модель преподавателя урока"""
    
    __tablename__ = "lesson_teachers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    biography: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now, onupdate=get_moscow_now)
    
    # Отношения
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="teacher")
    lesson_series: Mapped[list["LessonSeries"]] = relationship(back_populates="teacher")
    tests: Mapped[list["Test"]] = relationship(back_populates="teacher")
    
    def __repr__(self) -> str:
        return f"<LessonTeacher(id={self.id}, name='{self.name}')>"
    
    def __str__(self) -> str:
        return self.name
    
    @property
    def active_lessons_count(self) -> int:
        """Количество активных уроков преподавателя"""
        return len([lesson for lesson in self.lessons if lesson.is_active])