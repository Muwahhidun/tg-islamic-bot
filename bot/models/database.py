"""
Настройка базы данных и сессий
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from bot.utils.config import config


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


# Создание асинхронного движка
engine = create_async_engine(
    config.database_url,
    echo=config.debug,
    future=True
)

# Создание фабрики сессий
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_async_session() -> AsyncSession:
    """Получение асинхронной сессии"""
    async with async_session_maker() as session:
        yield session