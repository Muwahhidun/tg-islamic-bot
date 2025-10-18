# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Запуск и управление проектом

### Docker команды (основной способ запуска)
```bash
# Полный запуск проекта с инициализацией
docker-compose up -d --build

# Просмотр логов бота (обязательно для отладки)
docker-compose logs -f bot

# Инициализация начальных данных (только после первого запуска)
docker-compose exec bot python init_data.py

# Назначение прав администратора
docker-compose exec db psql -U postgres -d audio_bot -c "UPDATE users SET role_id = 1 WHERE telegram_id = ВАШ_TELEGRAM_ID;"

# Перезапуск бота
docker-compose restart bot

# Остановка всех сервисов
docker-compose down
```

### Работа с базой данных
```bash
# Подключение к PostgreSQL
docker-compose exec db psql -U postgres -d audio_bot

# Резервное копирование
docker-compose exec db pg_dump -U postgres audio_bot > backup.sql

# Восстановление из резервной копии
docker-compose exec -T db psql -U postgres audio_bot < backup.sql
```

## Критические особенности проекта

### Архитектура
- **Асинхронный Telegram бот** на aiogram 3.x с PostgreSQL
- **Модульная структура**: handlers/, models/, services/, utils/, keyboards/
- **Ролевая система**: admin (level=2), moderator (level=1), user (level=0)
- **Иерархия данных**: Темы → Книги → Уроки с аудиофайлами

### Важные паттерны кода

#### Декораторы безопасности
- `@admin_required` - проверка прав администратора
- `@moderator_required` - проверка прав модератора  
- `@user_required` - автоматическая регистрация пользователя
- `@error_handler` - обработка исключений с уведомлением пользователя

#### Работа с базой данных
- Используйте сервисные классы из `bot/services/database_service.py`
- Все сессии асинхронные: `async with async_session_maker() as session:`
- Модели используют SQLAlchemy 2.0 с async/await

#### FSM состояния
- Все многошаговые процессы используют aiogram FSM
- Не забывайте очищать состояние: `await state.clear()`

### Специфичные утилиты

#### AudioUtils (bot/utils/audio_utils.py)
- `validate_audio_file()` - проверка формата аудио
- `get_audio_duration()` - получение длительности через mutagen
- `save_audio_file()` - сохранение с уникальным именем
- `format_duration()` - форматирование секунд в ЧЧ:ММ:СС

#### Конфигурация (bot/utils/config.py)
- Все настройки через Pydantic Settings из .env файла
- `config.database_url` - автоформируемый URL для БД
- `config.allowed_audio_formats_list` - список разрешенных форматов

### Структура данных

#### Обязательные поля при создании сущностей
- **User**: telegram_id (уникальный), role_id (по умолчанию 3)
- **Lesson**: title, book_id, teacher_id, audio_path
- **Book**: name, theme_id, author_id
- **Theme**: name (уникальное)

#### Отношения в моделях
- Используйте `back_populates` для двусторонних связей
- `TYPE_CHECKING` для избежания циклических импортов

### Частые ошибки и их предотвращение

1. **Ошибка в about_project()** - функция не принимает параметр `user`
2. **Забыть await** - все операции с БД асинхронные
3. **Неправильная работа с файлами** - используйте AudioUtils для аудио
4. **Отсутствие очистки FSM** - всегда вызывайте `state.clear()`

### Тестирование и отладка

- Логи бота доступны через `docker-compose logs -f bot`
- Для отладки используйте уровень DEBUG в .env: `DEBUG=True`
- Проверка работы с БД через Adminer: http://localhost:8080

### Роли и права доступа

- **admin**: полный доступ ко всем функциям через `/admin`
- **moderator**: управление уроками и преподавателями
- **user**: просмотр и прослушивание контента

### Форматы аудиофайлов

Поддерживаемые форматы (настраиваются в .env):
- MP3, WAV, OGG, M4A
- Максимальный размер: 50 МБ (настраивается)