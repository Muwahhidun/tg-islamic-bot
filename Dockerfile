FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY bot/ ./bot/
COPY init_data.py ./

# Создание директории для аудио файлов
RUN mkdir -p /app/bot/audio_files

# Установка прав на выполнение
RUN chmod +x /app/bot/main.py

# Запуск приложения
CMD ["python", "-m", "bot.main"]