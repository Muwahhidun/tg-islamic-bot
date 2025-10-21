"""
Модель закладок пользователей
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.user import User
    from bot.models.lesson import Lesson


class Bookmark(Base):
    """Закладка пользователя на урок"""
    __tablename__ = "bookmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    custom_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=get_moscow_now, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="bookmarks")
    lesson: Mapped["Lesson"] = relationship()

    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint('user_id', 'lesson_id', name='uq_user_lesson_bookmark'),
        Index('ix_bookmarks_user_id', 'user_id'),
        Index('ix_bookmarks_lesson_id', 'lesson_id'),
    )

    def __repr__(self):
        return f"<Bookmark(id={self.id}, user_id={self.user_id}, lesson_id={self.lesson_id}, name='{self.custom_name}')>"
