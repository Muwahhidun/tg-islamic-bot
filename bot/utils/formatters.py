"""
Утилиты для форматирования данных
"""


def format_duration(seconds: int) -> str:
    """
    Форматирование длительности в читаемый вид

    Args:
        seconds: Длительность в секундах

    Returns:
        str: Отформатированная строка (например: "1ч 23м 45с")
    """
    if not seconds or seconds < 0:
        return "Неизвестно"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}ч {minutes}м {secs}с"
    elif minutes > 0:
        return f"{minutes}м {secs}с"
    else:
        return f"{secs}с"


def format_file_size(bytes_size: int) -> str:
    """
    Форматирование размера файла в читаемый вид

    Args:
        bytes_size: Размер в байтах

    Returns:
        str: Отформатированная строка (например: "12.3 МБ")
    """
    if not bytes_size or bytes_size < 0:
        return "0 Б"

    kb = bytes_size / 1024
    if kb < 1:
        return f"{bytes_size} Б"

    mb = kb / 1024
    if mb < 1:
        return f"{kb:.1f} КБ"

    gb = mb / 1024
    if gb < 1:
        return f"{mb:.1f} МБ"

    return f"{gb:.1f} ГБ"


def format_bitrate(bitrate: int) -> str:
    """
    Форматирование битрейта в читаемый вид

    Args:
        bitrate: Битрейт в bps (bits per second)

    Returns:
        str: Отформатированная строка (например: "128 kbps")
    """
    if not bitrate or bitrate < 0:
        return "Неизвестно"

    kbps = bitrate / 1000
    if kbps < 1000:
        return f"{int(kbps)} kbps"

    mbps = kbps / 1000
    return f"{mbps:.1f} Mbps"
