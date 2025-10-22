from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import String, Text, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.database import Base
from bot.utils.timezone_utils import get_moscow_now

if TYPE_CHECKING:
    from bot.models.user import User


class Feedback(Base):
    """
    Модель обратной связи от пользователей

    Статусы:
    - new: 🆕 Новое обращение
    - replied: ✅ Админ ответил
    - closed: 🔒 Обращение закрыто
    """
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Сообщение пользователя
    message_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Ответ админа (может быть NULL)
    admin_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Статус: new, replied, closed
    status: Mapped[str] = mapped_column(String(20), default="new", nullable=False, index=True)

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(default=get_moscow_now, nullable=False)
    replied_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Отношения
    user: Mapped["User"] = relationship(back_populates="feedbacks")

    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, user_id={self.user_id}, status='{self.status}')>"

    @property
    def status_emoji(self) -> str:
        """Эмодзи статуса"""
        status_map = {
            "new": "🆕",
            "replied": "✅",
            "closed": "🔒"
        }
        return status_map.get(self.status, "❓")

    @property
    def status_name(self) -> str:
        """Название статуса"""
        status_map = {
            "new": "Новое",
            "replied": "Отвечено",
            "closed": "Закрыто"
        }
        return status_map.get(self.status, "Неизвестно")
