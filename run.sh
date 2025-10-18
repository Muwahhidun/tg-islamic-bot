#!/bin/bash

# Скрипт для быстрого запуска и настройки Telegram бота

echo "🕌 Telegram бот для аудио уроков - Быстрый запуск"
echo "=============================================="

# Проверка наличия Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Пожалуйста, установите Docker."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен. Пожалуйста, установите Docker Compose."
    exit 1
fi

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден. Создаю из .env.example..."
    cp .env.example .env
    echo "⚠️  Пожалуйста, отредактируйте файл .env и добавьте ваш Telegram ID в ADMIN_TELEGRAM_ID"
    echo "   Токен бота уже добавлен в файл .env"
    read -p "Нажмите Enter после редактирования .env файла..."
fi

# Создание необходимых директорий
echo "📁 Создание директорий..."
mkdir -p bot/audio_files
mkdir -p logs
mkdir -p data/postgres/data

# Установка прав для директории PostgreSQL
echo "🔐 Настройка прав доступа..."
sudo chown -R 999:999 data/postgres 2>/dev/null || echo "⚠️  Не удалось изменить права доступа (требуются права sudo)"

# Сборка и запуск контейнеров
echo "🐳 Сборка и запуск контейнеров..."
docker-compose up -d --build

# Ожидание запуска базы данных
echo "⏳ Ожидание запуска базы данных..."
sleep 10

# Проверка статуса контейнеров
echo "📊 Проверка статуса контейнеров:"
docker-compose ps

# Инициализация данных
echo "📚 Инициализация начальных данных..."
docker-compose exec -T bot python init_data.py

echo ""
echo "✅ Бот успешно запущен!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Найдите вашего бота в Telegram и отправьте команду /start"
echo "2. Получите ваш Telegram ID: https://t.me/userinfobot"
echo "3. Выполните команду для назначения прав администратора:"
echo ""
echo "   docker-compose exec db psql -U postgres -d audio_bot -c \"UPDATE users SET role_id = 1 WHERE telegram_id = ВАШ_TELEGRAM_ID;\""
echo ""
echo "📱 Полезные команды:"
echo "   docker-compose logs -f bot     - просмотр логов бота"
echo "   docker-compose restart bot      - перезапуск бота"
echo "   docker-compose down             - остановка всех контейнеров"
echo ""
echo "🤲 Пусть Allah примет этот труд и сделает его полезным для уммы!"