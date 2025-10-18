"""
Модель тем
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base

if TYPE_CHECKING:
    from bot.models.book import Book


class Theme(Base):
    """Модель темы"""
    
    __tablename__ = "themes"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    books: Mapped[list["Book"]] = relationship(back_populates="theme", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Theme(id={self.id}, name='{self.name}')>"
    
    def __str__(self) -> str:
        return self.name
    
    @property
    def active_books_count(self) -> int:
        """Количество активных книг в теме"""
        return len([book for book in self.books if book.is_active])