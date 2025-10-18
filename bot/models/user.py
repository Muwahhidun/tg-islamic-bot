"""
Модель пользователей
"""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base

if TYPE_CHECKING:
    from bot.models.role import Role


class User(Base):
    """Модель пользователя"""
    
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str] = mapped_column(String(255), nullable=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id"), default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Отношения
    role: Mapped["Role"] = relationship(back_populates="users")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username='{self.username}')>"
    
    def __str__(self) -> str:
        if self.username:
            return f"@{self.username}"
        return f"{self.first_name or ''} {self.last_name or ''}".strip()
    
    @property
    def full_name(self) -> str:
        """Получение полного имени пользователя"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.username or "Unknown"
    
    @property
    def is_admin(self) -> bool:
        """Проверка, является ли пользователь администратором"""
        return self.role and self.role.level >= 2
    
    @property
    def is_moderator(self) -> bool:
        """Проверка, является ли пользователь модератором или администратором"""
        return self.role and self.role.level >= 1
    
    def has_permission(self, required_level: int) -> bool:
        """Проверка, имеет ли пользователь необходимый уровень доступа"""
        return self.role and self.role.level >= required_level