"""
Утилиты для конвертации аудио файлов через FFmpeg
"""
import subprocess
import os
import logging
import json
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)

# Константы для расчёта битрейта
MAX_OUTPUT_SIZE_MB = 49  # Максимальный размер выходного файла в МБ (оставляем запас)
MAX_OUTPUT_SIZE_BYTES = MAX_OUTPUT_SIZE_MB * 1024 * 1024
MIN_BITRATE_KBPS = 16  # Минимальный битрейт для приемлемого качества речи
MAX_BITRATE_KBPS = 128  # Максимальный битрейт для речи


async def calculate_optimal_bitrate(duration_seconds: int, target_size_mb: int = MAX_OUTPUT_SIZE_MB) -> int:
    """
    Расчёт оптимального битрейта для достижения целевого размера файла

    Формула: битрейт (kbps) = (размер_файла_в_байтах * 8) / (длительность_в_секундах * 1024)

    Args:
        duration_seconds: Длительность аудио в секундах
        target_size_mb: Целевой размер файла в МБ (по умолчанию 49 МБ)

    Returns:
        int: Оптимальный битрейт в kbps
    """
    if duration_seconds <= 0:
        logger.warning(f"Некорректная длительность: {duration_seconds}, используем битрейт по умолчанию")
        return 64

    target_size_bytes = target_size_mb * 1024 * 1024

    # Расчёт битрейта: (размер в битах) / (длительность в секундах) / 1024 = kbps
    calculated_bitrate = int((target_size_bytes * 8) / (duration_seconds * 1024))

    # Ограничиваем битрейт разумными пределами
    optimal_bitrate = max(MIN_BITRATE_KBPS, min(calculated_bitrate, MAX_BITRATE_KBPS))

    logger.info(f"Расчёт битрейта: длительность={duration_seconds}с, целевой размер={target_size_mb}МБ, "
                f"рассчитанный битрейт={calculated_bitrate}kbps, оптимальный={optimal_bitrate}kbps")

    return optimal_bitrate


async def convert_to_mp3(
    input_path: str,
    output_path: str,
    bitrate: str = "64k",
    channels: int = 1,
    sample_rate: int = 44100,
    normalize: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Конвертация аудио файла в MP3 с нормализацией громкости

    Args:
        input_path: Путь к исходному аудио файлу
        output_path: Путь для сохранения MP3 файла
        bitrate: Битрейт (по умолчанию 64k для речи)
        channels: Количество каналов (1 = mono, 2 = stereo)
        sample_rate: Частота дискретизации в Гц
        normalize: Применять ли нормализацию громкости

    Returns:
        Tuple[bool, Optional[str]]: (успех, сообщение об ошибке)
    """
    try:
        # Проверка существования входного файла
        if not os.path.exists(input_path):
            return False, f"Входной файл не найден: {input_path}"

        # Создание директории для выходного файла
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # Построение команды FFmpeg
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-codec:a", "libmp3lame",
            "-b:a", bitrate,
            "-ac", str(channels),
            "-ar", str(sample_rate),
        ]

        # Добавление фильтра нормализации громкости
        if normalize:
            cmd.extend([
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11"
            ])

        # Перезапись файла без запроса
        cmd.extend(["-y", output_path])

        logger.info(f"Запуск конвертации: {input_path} -> {output_path}")
        logger.debug(f"FFmpeg команда: {' '.join(cmd)}")

        # Запуск FFmpeg
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600  # Тайм-аут 10 минут
        )

        if process.returncode != 0:
            error_message = process.stderr.decode('utf-8', errors='ignore')
            logger.error(f"Ошибка FFmpeg: {error_message}")
            return False, f"Ошибка конвертации: {error_message[:200]}"

        # Проверка, что выходной файл создан
        if not os.path.exists(output_path):
            return False, "Выходной файл не был создан"

        # Проверка размера выходного файла
        output_size = os.path.getsize(output_path)
        if output_size == 0:
            return False, "Выходной файл пустой"

        logger.info(f"Конвертация успешна: {output_path} ({output_size} байт)")
        return True, None

    except subprocess.TimeoutExpired:
        logger.error(f"Тайм-аут конвертации: {input_path}")
        return False, "Превышено время ожидания конвертации (10 минут)"
    except Exception as e:
        logger.error(f"Ошибка при конвертации {input_path}: {str(e)}")
        return False, f"Неожиданная ошибка: {str(e)}"


async def convert_to_mp3_auto(
    input_path: str,
    output_path: str,
    preferred_bitrate: int = 64,
    channels: int = 1,
    sample_rate: int = 44100,
    normalize: bool = True,
    max_attempts: int = 2
) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Автоматическая конвертация аудио в MP3 с подбором оптимального битрейта

    Сначала пробует конвертировать с предпочтительным битрейтом (64 kbps).
    Если файл получается > 50 МБ, пересчитывает битрейт и конвертирует заново.

    Args:
        input_path: Путь к исходному аудио файлу
        output_path: Путь для сохранения MP3 файла
        preferred_bitrate: Предпочтительный битрейт в kbps (по умолчанию 64)
        channels: Количество каналов (1 = mono, 2 = stereo)
        sample_rate: Частота дискретизации в Гц
        normalize: Применять ли нормализацию громкости
        max_attempts: Максимальное количество попыток конвертации

    Returns:
        Tuple[bool, Optional[str], Optional[int]]:
            (успех, сообщение об ошибке, использованный битрейт в kbps)
    """
    try:
        # Сначала получаем длительность оригинального файла
        duration = await get_audio_duration(input_path)
        if duration is None:
            return False, "Не удалось определить длительность файла", None

        logger.info(f"Длительность файла: {duration} секунд ({duration // 60} минут)")

        # Попытка 1: Конвертация с предпочтительным битрейтом
        bitrate_kbps = preferred_bitrate
        logger.info(f"Попытка 1: Конвертация с битрейтом {bitrate_kbps} kbps")

        success, error = await convert_to_mp3(
            input_path, output_path,
            bitrate=f"{bitrate_kbps}k",
            channels=channels,
            sample_rate=sample_rate,
            normalize=normalize
        )

        if not success:
            return False, error, None

        # Проверяем размер получившегося файла
        output_size = os.path.getsize(output_path)
        output_size_mb = output_size / (1024 * 1024)

        logger.info(f"Размер выходного файла: {output_size_mb:.2f} МБ")

        # Если файл влезает в лимит - отлично!
        if output_size <= MAX_OUTPUT_SIZE_BYTES:
            logger.info(f"✅ Файл успешно сконвертирован ({output_size_mb:.2f} МБ, {bitrate_kbps} kbps)")
            return True, None, bitrate_kbps

        # Попытка 2: Файл слишком большой, рассчитываем оптимальный битрейт
        logger.warning(f"Файл слишком большой ({output_size_mb:.2f} МБ), пересчитываем битрейт...")

        optimal_bitrate = await calculate_optimal_bitrate(duration, MAX_OUTPUT_SIZE_MB)

        if optimal_bitrate < MIN_BITRATE_KBPS:
            return False, (
                f"Файл слишком длинный ({duration // 60} минут). "
                f"Для размещения требуется битрейт < {MIN_BITRATE_KBPS} kbps (неприемлемое качество). "
                f"Пожалуйста, разделите урок на части по 1-2 часа."
            ), None

        logger.info(f"Попытка 2: Конвертация с оптимальным битрейтом {optimal_bitrate} kbps")

        # Удаляем предыдущий файл
        if os.path.exists(output_path):
            os.remove(output_path)

        # Конвертируем с оптимальным битрейтом
        success, error = await convert_to_mp3(
            input_path, output_path,
            bitrate=f"{optimal_bitrate}k",
            channels=channels,
            sample_rate=sample_rate,
            normalize=normalize
        )

        if not success:
            return False, error, None

        # Финальная проверка размера
        final_size = os.path.getsize(output_path)
        final_size_mb = final_size / (1024 * 1024)

        logger.info(f"Финальный размер: {final_size_mb:.2f} МБ с битрейтом {optimal_bitrate} kbps")

        if final_size > MAX_OUTPUT_SIZE_BYTES:
            return False, (
                f"Не удалось уменьшить файл до 50 МБ. "
                f"Итоговый размер: {final_size_mb:.2f} МБ. "
                f"Пожалуйста, разделите урок на части."
            ), optimal_bitrate

        logger.info(f"✅ Файл успешно сконвертирован ({final_size_mb:.2f} МБ, {optimal_bitrate} kbps)")
        return True, None, optimal_bitrate

    except Exception as e:
        logger.error(f"Ошибка при автоматической конвертации {input_path}: {str(e)}")
        return False, f"Неожиданная ошибка: {str(e)}", None


async def get_audio_duration(file_path: str) -> Optional[int]:
    """
    Получение длительности аудио файла в секундах через FFprobe

    Args:
        file_path: Путь к аудио файлу

    Returns:
        int: Длительность в секундах или None при ошибке
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"Файл не найден: {file_path}")
            return None

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]

        logger.debug(f"FFprobe команда: {' '.join(cmd)}")

        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )

        if process.returncode != 0:
            error_message = process.stderr.decode('utf-8', errors='ignore')
            logger.error(f"Ошибка FFprobe: {error_message}")
            return None

        duration_str = process.stdout.decode('utf-8').strip()
        duration_seconds = int(float(duration_str))

        logger.info(f"Длительность {file_path}: {duration_seconds} секунд")
        return duration_seconds

    except subprocess.TimeoutExpired:
        logger.error(f"Тайм-аут получения длительности: {file_path}")
        return None
    except (ValueError, TypeError) as e:
        logger.error(f"Ошибка парсинга длительности для {file_path}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении длительности {file_path}: {str(e)}")
        return None


async def get_audio_info(file_path: str) -> Optional[Dict[str, any]]:
    """
    Получение полной информации об аудио файле через FFprobe

    Args:
        file_path: Путь к аудио файлу

    Returns:
        Dict: Словарь с информацией о файле или None при ошибке
        {
            'duration': int,      # секунды
            'format': str,        # формат (mp3, wav, etc.)
            'bitrate': int,       # битрейт в bps
            'sample_rate': int,   # частота дискретизации
            'channels': int,      # количество каналов
            'size': int           # размер файла в байтах
        }
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"Файл не найден: {file_path}")
            return None

        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-of", "json",
            file_path
        ]

        logger.debug(f"FFprobe команда: {' '.join(cmd)}")

        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30
        )

        if process.returncode != 0:
            error_message = process.stderr.decode('utf-8', errors='ignore')
            logger.error(f"Ошибка FFprobe: {error_message}")
            return None

        data = json.loads(process.stdout.decode('utf-8'))

        # Извлечение информации о формате
        format_info = data.get('format', {})

        # Извлечение информации об аудио потоке
        audio_stream = None
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'audio':
                audio_stream = stream
                break

        if not audio_stream:
            logger.error(f"Аудио поток не найден в файле: {file_path}")
            return None

        info = {
            'duration': int(float(format_info.get('duration', 0))),
            'format': format_info.get('format_name', 'unknown'),
            'bitrate': int(format_info.get('bit_rate', 0)),
            'sample_rate': int(audio_stream.get('sample_rate', 0)),
            'channels': int(audio_stream.get('channels', 0)),
            'size': int(format_info.get('size', os.path.getsize(file_path)))
        }

        logger.info(f"Информация о файле {file_path}: {info}")
        return info

    except subprocess.TimeoutExpired:
        logger.error(f"Тайм-аут получения информации: {file_path}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON для {file_path}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Ошибка при получении информации о {file_path}: {str(e)}")
        return None
