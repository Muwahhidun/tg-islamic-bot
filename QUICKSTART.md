# Быстрый старт с Telegram ботом для аудио уроков

## 🚀 Быстрое развертывание

### 1. Клонирование и настройка

```bash
# Клонирование проекта
git clone <repository_url>
cd telegram_audio_bot

# Создание файла конфигурации
cp .env.example .env

# Редактирование файла .env
nano .env
```

### 2. Настройка переменных окружения

Обязательно заполните следующие параметры в `.env` файле:

```env
# Telegram Bot Token - получите от @BotFather
BOT_TOKEN=your_telegram_bot_token_here

# Database Configuration
DB_HOST=db
DB_PORT=5432
DB_NAME=audio_bot
DB_USER=postgres
DB_PASSWORD=your_secure_postgres_password_here

# Admin Configuration - ваш Telegram ID
ADMIN_TELEGRAM_ID=your_admin_telegram_id_here
```

### 3. Запуск проекта

```bash
# Сборка и запуск контейнеров
docker-compose up -d --build

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f bot
```

### 4. Инициализация данных

После первого запуска выполните инициализацию начальных данных:

```bash
# Выполнение скрипта инициализации
docker-compose exec bot python init_data.py
```

### 5. Настройка администратора

1. Найдите вашего бота в Telegram и отправьте команду `/start`
2. Выполните команду для назначения прав администратора:

```bash
# Подключение к базе данных
docker-compose exec db psql -U postgres -d audio_bot

# Обновление роли пользователя до администратора
UPDATE users SET role_id = 1 WHERE telegram_id = ВАШ_TELEGRAM_ID;
```

## 📱 Использование бота

### Для пользователей

1. Отправьте команду `/start` для регистрации
2. Используйте меню для навигации:
   - 📚 Список тем - просмотр доступных тем
   - 🔍 Поиск уроков - поиск по ключевым словам
   - ℹ️ О проекте - информация о проекте

### Для администраторов

После назначения прав администратора вам будет доступна команда `/admin` с полным функционалом управления.

## 🔧 Полезные команды

### Управление контейнерами

```bash
# Просмотр логов бота
docker-compose logs -f bot

# Перезапуск бота
docker-compose restart bot

# Остановка всех контейнеров
docker-compose down

# Полная переустановка
docker-compose down -v
docker-compose up -d --build
```

### Работа с базой данных

```bash
# Подключение к базе данных
docker-compose exec db psql -U postgres -d audio_bot

# Просмотр таблиц
\dt

# Просмотр пользователей
SELECT * FROM users;

# Просмотр тем
SELECT * FROM themes;

# Создание резервной копии
docker-compose exec db pg_dump -U postgres audio_bot > backup.sql
```

## 📝 Добавление аудиофайлов

Для добавления аудиофайлов:

1. Поместите аудиофайлы в директорию `bot/audio_files/`
2. Используйте административную панель бота для добавления уроков
3. Укажите путь к аудиофайлу при создании урока

## 🐛 Решение проблем

### Бот не отвечает

1. Проверьте логи: `docker-compose logs bot`
2. Убедитесь, что токен бота правильный
3. Проверьте подключение к интернету

### Проблемы с базой данных

1. Проверьте статус контейнера: `docker-compose ps`
2. Проверьте логи: `docker-compose logs db`
3. Убедитесь, что пароль в `.env` совпадает с паролем в `docker-compose.yml`

### Аудиофайлы не воспроизводятся

1. Проверьте наличие файлов: `ls -la bot/audio_files/`
2. Убедитесь, что формат файла поддерживается (mp3, wav, ogg, m4a)
3. Проверьте права доступа к файлам

## 📞 Поддержка

Если возникли проблемы:

1. Проверьте логи контейнеров
2. Изучите документацию в файлах `*.md`
3. Создайте issue в репозитории проекта

---

🤲 *Пусть Allah примет этот труд и сделает его полезным для уммы!*