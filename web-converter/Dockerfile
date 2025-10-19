FROM python:3.11-slim

# Установка системных зависимостей (FFmpeg)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    locales \
    && rm -rf /var/lib/apt/lists/*

# Настройка русской локали
RUN sed -i -e 's/# ru_RU.UTF-8 UTF-8/ru_RU.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen

ENV LANG=ru_RU.UTF-8
ENV LANGUAGE=ru_RU:ru
ENV LC_ALL=ru_RU.UTF-8

# Рабочая директория
WORKDIR /app

# Копируем requirements для веб-сервиса
COPY web-converter/requirements.txt ./web-converter/

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r web-converter/requirements.txt

# Копируем утилиты бота (для переиспользования FFmpeg функций)
COPY bot/utils/ ./bot/utils/
COPY bot/__init__.py ./bot/

# Копируем код веб-сервиса
COPY web-converter/main.py ./web-converter/

# Создаём директории для файлов
RUN mkdir -p /app/web-converter/uploads /app/web-converter/converted

# Запуск
CMD ["python", "-m", "uvicorn", "web-converter.main:app", "--host", "0.0.0.0", "--port", "1992"]
