FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    ffmpeg \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Настройка русской локали
RUN sed -i -e 's/# ru_RU.UTF-8 UTF-8/ru_RU.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen

ENV LANG=ru_RU.UTF-8
ENV LANGUAGE=ru_RU:ru
ENV LC_ALL=ru_RU.UTF-8

# Установка рабочей директории
WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY bot/ ./bot/
COPY init_data.py ./
COPY migrate_to_lesson_series.py ./

# Создание директорий для аудио файлов
RUN mkdir -p /app/bot/audio_files/original /app/bot/audio_files/converted

# Установка прав на выполнение
RUN chmod +x /app/bot/main.py

# Запуск приложения
CMD ["python", "-m", "bot.main"]