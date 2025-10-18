# Инструкция по развертыванию Telegram бота для аудио уроков

## Требования к системе

### Минимальные требования
- Docker 20.10+
- Docker Compose 2.0+
- 2 ГБ оперативной памяти
- 10 ГБ свободного дискового пространства (для аудиофайлов)

### Рекомендуемые требования
- 4 ГБ оперативной памяти
- 50 ГБ свободного дискового пространства
- Стабильное интернет-соединение

## Пошаговая инструкция по развертыванию

### Шаг 1: Подготовка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Проверка установки
docker --version
docker-compose --version
```

### Шаг 2: Клонирование и настройка проекта

```bash
# Клонирование репозитория
git clone <repository_url>
cd telegram_audio_bot

# Создание необходимых директорий
mkdir -p bot/audio_files
mkdir -p data/postgres/data
mkdir -p logs
```

### Шаг 3: Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
# Telegram Bot Token
BOT_TOKEN=your_telegram_bot_token_here

# Database Configuration
DB_HOST=db
DB_PORT=5432
DB_NAME=audio_bot
DB_USER=postgres
DB_PASSWORD=your_secure_postgres_password_here

# Admin Configuration
ADMIN_TELEGRAM_ID=your_admin_telegram_id_here

# Application Configuration
DEBUG=False
LOG_LEVEL=INFO

# File Configuration
MAX_AUDIO_SIZE_MB=50
ALLOWED_AUDIO_FORMATS=mp3,wav,ogg,m4a
```

### Шаг 4: Получение токена Telegram бота

1. Найдите [@BotFather](https://t.me/botfather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания бота
4. Скопируйте полученный токен в `.env` файл

### Шаг 5: Настройка прав доступа к файлам

```bash
# Установка прав для директории аудиофайлов
sudo chown -R $USER:$USER bot/audio_files
chmod -R 755 bot/audio_files

# Установка прав для директории данных PostgreSQL
sudo chown -R 999:999 data/postgres
```

### Шаг 6: Сборка и запуск контейнеров

```bash
# Сборка образов
docker-compose build

# Запуск контейнеров в фоновом режиме
docker-compose up -d

# Проверка статуса контейнеров
docker-compose ps
```

### Шаг 7: Инициализация базы данных

```bash
# Проверка логов для уверенности, что БД запустилась
docker-compose logs db

# Подключение к базе данных для проверки
docker-compose exec db psql -U postgres -d audio_bot -c "\dt"
```

### Шаг 8: Настройка администратора

После первого запуска бота, отправьте ему команду `/start`, а затем выполните:

```bash
# Подключение к базе данных
docker-compose exec db psql -U postgres -d audio_bot

# Обновление роли пользователя до администратора
UPDATE users SET role_id = 1 WHERE telegram_id = your_admin_telegram_id_here;
```

## Проверка работоспособности

### Проверка бота
1. Найдите вашего бота в Telegram по username
2. Отправьте команду `/start`
3. Убедитесь, что бот отвечает и показывает главное меню

### Проверка административной панели
1. Отправьте команду `/admin`
2. Убедитесь, что открывается панель администратора

### Проверка базы данных
```bash
# Подключение к БД
docker-compose exec db psql -U postgres -d audio_bot

# Проверка таблиц
\dt

# Проверка начальных данных
SELECT * FROM roles;
SELECT * FROM themes;
SELECT * FROM book_authors;
SELECT * FROM lesson_teachers;
```

## Управление проектом

### Просмотр логов
```bash
# Логи бота
docker-compose logs -f bot

# Логи базы данных
docker-compose logs -f db

# Все логи
docker-compose logs -f
```

### Обновление проекта
```bash
# Остановка контейнеров
docker-compose down

# Получение обновлений
git pull

# Пересборка и запуск
docker-compose up -d --build
```

### Резервное копирование

#### Резервное копирование базы данных
```bash
# Создание бэкапа
docker-compose exec db pg_dump -U postgres audio_bot > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановление из бэкапа
docker-compose exec -T db psql -U postgres audio_bot < backup_20231201_120000.sql
```

#### Резервное копирование аудиофайлов
```bash
# Создание архива с аудиофайлами
tar -czf audio_backup_$(date +%Y%m%d_%H%M%S).tar.gz bot/audio_files/
```

### Автоматическое резервное копирование

Создайте скрипт `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Создание директории для бэкапов
mkdir -p $BACKUP_DIR

# Бэкап базы данных
docker-compose exec -T db pg_dump -U postgres audio_bot > $BACKUP_DIR/db_backup_$DATE.sql

# Бэкап аудиофайлов
tar -czf $BACKUP_DIR/audio_backup_$DATE.tar.gz bot/audio_files/

# Удаление старых бэкапов (старше 7 дней)
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

Добавьте в cron для автоматического запуска:
```bash
# Открыть crontab
crontab -e

# Добавить строку для ежедневного бэкапа в 3 часа ночи
0 3 * * * /path/to/backup.sh >> /var/log/backup.log 2>&1
```

## Мониторинг

### Мониторинг контейнеров
```bash
# Проверка использования ресурсов
docker stats

# Проверка дискового пространства
df -h

# Проверка использования памяти
free -h
```

### Мониторинг базы данных
```bash
# Подключение к БД
docker-compose exec db psql -U postgres -d audio_bot

# Просмотр активных соединений
SELECT * FROM pg_stat_activity;

# Просмотр размера таблиц
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Безопасность

### Настройка файрвола
```bash
# Разрешение только необходимых портов
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP (если нужен веб-интерфейс)
sudo ufw allow 443   # HTTPS (если нужен веб-интерфейс)
sudo ufw enable
```

### Регулярное обновление
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Обновление Docker образов
docker-compose pull
docker-compose up -d
```

## Решение проблем

### Бот не отвечает
1. Проверьте логи: `docker-compose logs bot`
2. Проверьте токен в `.env` файле
3. Проверьте подключение к интернету
4. Перезапустите контейнер: `docker-compose restart bot`

### Проблемы с базой данных
1. Проверьте логи: `docker-compose logs db`
2. Проверьте пароль в `.env` файле
3. Проверьте доступное дисковое пространство
4. Перезапустите контейнер: `docker-compose restart db`

### Проблемы с аудиофайлами
1. Проверьте права доступа к директории `bot/audio_files`
2. Проверьте доступное дисковое пространство
3. Проверьте формат аудиофайла
4. Проверьте размер файла (не превышает лимит)

## Масштабирование

### Увеличение дискового пространства
1. Остановите контейнеры: `docker-compose down`
2. Добавьте новый диск или увеличьте существующий
3. Измените точки монтирования в `docker-compose.yml`
4. Запустите контейнеры: `docker-compose up -d`

### Оптимизация производительности
1. Настройте индексы в базе данных
2. Настройте кэширование Redis (при необходимости)
3. Используйте CDN для аудиофайлов
4. Настройте балансировку нагрузки

## Поддержка

Если возникли проблемы:
1. Проверьте логи контейнеров
2. Проверьте официальную документацию Docker и PostgreSQL
3. Создайте issue в репозитории проекта
4. Свяжитесь с командой разработки