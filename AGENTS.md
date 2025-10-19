# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Критические особенности проекта (неочевидные паттерны)

### Декораторы безопасности (критически важно)
- `@user_required` изменяет сигнатуру функции - добавляет параметр `user` если он ожидается
- Порядок декораторов важен: `@user_required` должен быть первым перед `@admin_required`
- `@clear_state` автоматически очищает FSM состояние после выполнения функции

### Работа с базой данных
- ВСЕ операции с БД должны использовать сервисные классы из `bot/services/database_service.py`
- Сессии только асинхронные: `async with async_session_maker() as session:`
- Используйте `joinedload()` для предварительной загрузки связей, избегайте N+1 запросов

### Обработка аудиофайлов
- ВСЕГДА используйте `AudioUtils.validate_audio_file()` перед сохранением
- Файлы сохраняются с уникальными именами через `AudioUtils.save_audio_file()` (не перезаписывайте)
- Проверка размера через `AudioUtils.is_file_size_valid()` перед обработкой

### Конфигурация
- `config.database_url` формируется автоматически, не создавайте вручную
- `config.max_audio_size_bytes` вычисляется из МБ, используйте это свойство
- `config.allowed_audio_formats_list` получает список из строки через запятую

### Модели данных
- Используйте `TYPE_CHECKING` для избежания циклических импортов в моделях
- `back_populates` для двусторонних связей (не `relationship()` без параметров)
- Обязательные поля: User.telegram_id, Lesson.title/book_id/teacher_id

### FSM состояния
- ВСЕГДА очищайте состояние: `await state.clear()` после завершения
- Используйте декоратор `@clear_state` для автоматической очистки
- Проверяйте данные состояния через `await state.get_data()` при отладке

### Обработчики
- Пользовательские обработчики в `bot/handlers/user.py`
- Административные в `bot/handlers/admin/` (раздельные файлы)
- ВСЕ колбэки должны иметь `await callback.answer()`

### Отладка
- Включите `DEBUG=True` в .env для логирования SQL запросов
- Используйте `docker-compose logs -f bot` для просмотра логов в реальном времени
- Проверяйте права доступа через `/id` команду

### Запуск проекта
```bash
# Полный запуск с инициализацией
docker-compose up -d --build

# Инициализация начальных данных (только после первого запуска)
docker-compose exec bot python init_data.py

# Назначение прав администратора
docker-compose exec db psql -U postgres -d audio_bot -c "UPDATE users SET role_id = 1 WHERE telegram_id = ВАШ_TELEGRAM_ID;"
```