"""
Утилиты для работы с временными зонами
"""
from datetime import datetime
import pytz

# Московская временная зона (UTC+3)
MOSCOW_TZ = pytz.timezone('Europe/Moscow')


def get_moscow_now() -> datetime:
    """
    Получение текущего времени в Москве (UTC+3)

    Возвращает naive datetime (без timezone), так как PostgreSQL
    настроен на московское время через PGTZ=Europe/Moscow

    Returns:
        datetime: Текущее время в московском времени (timezone-naive)
    """
    return datetime.now(MOSCOW_TZ).replace(tzinfo=None)


def utc_to_moscow(utc_dt: datetime) -> datetime:
    """
    Конвертация UTC времени в московское время

    Args:
        utc_dt: UTC datetime объект

    Returns:
        datetime: Время в московской зоне
    """
    if utc_dt.tzinfo is None:
        # Если время naive, считаем его UTC
        utc_dt = pytz.utc.localize(utc_dt)
    return utc_dt.astimezone(MOSCOW_TZ)


def moscow_to_utc(moscow_dt: datetime) -> datetime:
    """
    Конвертация московского времени в UTC

    Args:
        moscow_dt: Московское datetime объект

    Returns:
        datetime: Время в UTC
    """
    if moscow_dt.tzinfo is None:
        # Если время naive, считаем его московским
        moscow_dt = MOSCOW_TZ.localize(moscow_dt)
    return moscow_dt.astimezone(pytz.utc)
