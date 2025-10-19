"""
Модель авторов книг
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.book import Book


class BookAuthor(Base):
    """Модель автора книги"""
    
    __tablename__ = "book_authors"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    biography: Mapped[str] = mapped_column(Text, nullable=True)
    birth_year: Mapped[int] = mapped_column(Integer, nullable=True)
    death_year: Mapped[int] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now, onupdate=get_moscow_now)
    
    # Отношения
    books: Mapped[list["Book"]] = relationship(back_populates="author")
    
    def __repr__(self) -> str:
        return f"<BookAuthor(id={self.id}, name='{self.name}')>"
    
    def __str__(self) -> str:
        return self.name
    
    @property
    def life_years(self) -> str:
        """Получение строкового представления лет жизни"""
        if self.birth_year and self.death_year:
            return f"({self.birth_year}-{self.death_year})"
        elif self.birth_year:
            return f"(р. {self.birth_year})"
        return ""
    
    @property
    def full_name_with_years(self) -> str:
        """Получение полного имени с годами жизни"""
        years = self.life_years
        if years:
            return f"{self.name} {years}"
        return self.name
    
    @property
    def active_books_count(self) -> int:
        """Количество активных книг автора"""
        return len([book for book in self.books if book.is_active])