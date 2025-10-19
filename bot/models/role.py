"""
Модель ролей пользователей
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.user import User


class Role(Base):
    """Модель роли пользователя"""
    
    __tablename__ = "roles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=get_moscow_now)
    
    # Отношения
    users: Mapped[list["User"]] = relationship(back_populates="role")
    
    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}', level={self.level})>"
    
    def __str__(self) -> str:
        return self.name