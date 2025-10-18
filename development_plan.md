# План разработки Telegram бота для аудио уроков

## Этапы разработки

### Этап 1: Настройка инфраструктуры (1-2 дня)

#### 1.1 Создание структуры проекта
- Создание директорий согласно архитектуре
- Настройка виртуального окружения
- Установка зависимостей

#### 1.2 Настройка Docker окружения
- Создание Dockerfile для приложения
- Настройка docker-compose.yml с PostgreSQL
- Создание .env файла с конфигурацией
- Настройка томов для аудиофайлов

#### 1.3 Инициализация базы данных
- Создание SQL скрипта инициализации
- Настройка подключения к PostgreSQL
- Создание миграций с помощью Alembic

### Этап 2: Основной функционал бота (3-4 дня)

#### 2.1 Базовая структура бота
```python
# bot/main.py - основная точка входа
async def main():
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    
    # Регистрация хэндлеров
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
```

#### 2.2 Модели данных (SQLAlchemy)
```python
# bot/models/user.py
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))
    role_id = Column(Integer, ForeignKey("roles.id"), default=3)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

#### 2.3 Сервисы для работы с БД
```python
# bot/services/database.py
async def get_user(telegram_id: int) -> Optional[User]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

async def create_user(telegram_id: int, username: str, first_name: str, last_name: str) -> User:
    async with async_session() as session:
        user = User(telegram_id=telegram_id, username=username, 
                   first_name=first_name, last_name=last_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
```

### Этап 3: Система аутентификации и ролей (2-3 дня)

#### 3.1 Декораторы для проверки прав доступа
```python
# bot/utils/decorators.py
def admin_required(func):
    async def wrapper(message: types.Message, *args, **kwargs):
        user = await get_user(message.from_user.id)
        if user and user.role.level >= 2:
            return await func(message, *args, **kwargs)
        await message.answer("🚫 У вас нет прав для выполнения этой команды")
    return wrapper

def moderator_required(func):
    async def wrapper(message: types.Message, *args, **kwargs):
        user = await get_user(message.from_user.id)
        if user and user.role.level >= 1:
            return await func(message, *args, **kwargs)
        await message.answer("🚫 У вас нет прав для выполнения этой команды")
    return wrapper
```

#### 3.2 Сервис аутентификации
```python
# bot/services/auth_service.py
class AuthService:
    async def register_user(self, telegram_user: types.User) -> User:
        user = await get_user(telegram_user.id)
        if not user:
            user = await create_user(
                telegram_id=telegram_user.id,
                username=telegram_user.username,
                first_name=telegram_user.first_name,
                last_name=telegram_user.last_name
            )
        return user
    
    async def set_admin_role(self, telegram_id: int) -> bool:
        async with async_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalar_one_or_none()
            if user:
                user.role_id = 1  # admin role
                await session.commit()
                return True
            return False
```

### Этап 4: Пользовательский интерфейс (3-4 дня)

#### 4.1 Главное меню
```python
# bot/handlers/user.py
@router.message(CommandStart())
async def cmd_start(message: types.Message):
    user = await auth_service.register_user(message.from_user)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Список тем")],
            [KeyboardButton(text="🔍 Поиск уроков")],
            [KeyboardButton(text="ℹ️ О проекте")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        f"🕌 Добро пожаловать, {message.from_user.first_name}!\n\n"
        "Здесь вы найдете аудио уроки по исламским наукам.",
        reply_markup=keyboard
    )
```

#### 4.2 Просмотр тем и книг
```python
@router.message(F.text == "📚 Список тем")
async def show_themes(message: types.Message):
    themes = await get_active_themes()
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=theme.name, callback_data=f"theme_{theme.id}")]
            for theme in themes
        ]
    )
    
    await message.answer("📚 Выберите тему:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("theme_"))
async def show_books(callback: types.CallbackQuery):
    theme_id = int(callback.data.split("_")[1])
    books = await get_active_books_by_theme(theme_id)
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=book.name, callback_data=f"book_{book.id}")]
            for book in books
        ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_themes")]]
    )
    
    await callback.message.edit_text(
        f"📖 Книги в теме:\n\n" + 
        "\n".join([f"• {book.name}" for book in books]),
        reply_markup=keyboard
    )
```

### Этап 5: Административная панель (4-5 дней)

#### 5.1 Панель администратора
```python
# bot/handlers/admin.py
@router.message(Command("admin"))
@admin_required
async def admin_panel(message: types.Message):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📚 Управление темами")],
            [KeyboardButton(text="📖 Управление книгами")],
            [KeyboardButton(text="🎧 Управление уроками")],
            [KeyboardButton(text="👥 Управление пользователями")],
            [KeyboardButton(text="📊 Статистика")],
            [KeyboardButton(text="⬅️ Выйти из админки")]
        ],
        resize_keyboard=True
    )
    
    await message.answer("🛠️ Панель администратора", reply_markup=keyboard)
```

#### 5.2 Добавление урока
```python
@router.message(F.text == "➕ Добавить урок")
@moderator_required
async def add_lesson_start(message: types.Message):
    # Создаем состояние для добавления урока
    state = FSMContext(dp.storage, message.chat.id, message.chat.id)
    await state.set_state(AddLesson.book_selection)
    
    books = await get_all_books()
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=book.name, callback_data=f"select_book_{book.id}")]
            for book in books
        ]
    )
    
    await message.answer("Выберите книгу для добавления урока:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("select_book_"))
async def select_book_for_lesson(callback: types.CallbackQuery, state: FSMContext):
    book_id = int(callback.data.split("_")[2])
    await state.update_data(book_id=book_id)
    await state.set_state(AddLesson.title_input)
    
    await callback.message.edit_text("Введите название урока:")
```

### Этап 6: Работа с аудиофайлами (3-4 дня)

#### 6.1 Загрузка и обработка аудио
```python
# bot/services/audio_service.py
class AudioService:
    async def process_audio(self, message: types.Message, book_id: int, lesson_data: dict) -> Lesson:
        # Скачивание аудиофайла
        file = await message.bot.get_file(message.audio.file_id)
        file_path = file.file_path
        
        # Генерация уникального имени файла
        unique_filename = f"{uuid.uuid4()}.mp3"
        local_path = f"audio_files/{unique_filename}"
        
        # Скачивание файла
        await message.bot.download_file(file_path, local_path)
        
        # Получение длительности аудио
        duration = await self.get_audio_duration(local_path)
        
        # Сохранение в БД
        lesson = await create_lesson(
            book_id=book_id,
            title=lesson_data["title"],
            description=lesson_data.get("description", ""),
            audio_path=local_path,
            lesson_number=lesson_data.get("lesson_number"),
            duration_seconds=duration,
            tags=lesson_data.get("tags", "")
        )
        
        return lesson
    
    async def get_audio_duration(self, file_path: str) -> int:
        # Использование mutagen для получения длительности
        from mutagen.mp3 import MP3
        audio = MP3(file_path)
        return int(audio.info.length)
```

#### 6.2 Отправка аудио пользователю
```python
@router.callback_query(F.data.startswith("lesson_"))
async def play_lesson(callback: types.CallbackQuery):
    lesson_id = int(callback.data.split("_")[1])
    lesson = await get_lesson(lesson_id)
    
    if not lesson or not lesson.audio_path:
        await callback.answer("❌ Аудиофайл не найден", show_alert=True)
        return
    
    # Создание клавиатуры управления
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Предыдущий", callback_data=f"prev_{lesson_id}")],
            [InlineKeyboardButton(text="➡️ Следующий", callback_data=f"next_{lesson_id}")],
            [InlineKeyboardButton(text="⬅️ К книге", callback_data=f"back_to_book_{lesson.book_id}")]
        ]
    )
    
    # Отправка аудиофайла
    with open(lesson.audio_path, 'rb') as audio_file:
        await callback.message.answer_audio(
            audio=audio_file,
            title=lesson.title,
            caption=f"📖 {lesson.title}\n\n{lesson.description}",
            reply_markup=keyboard
        )
```

### Этап 7: Продвинутый функционал (2-3 дня)

#### 7.1 Поиск уроков
```python
@router.message(F.text == "🔍 Поиск уроков")
async def search_lessons(message: types.Message):
    await message.answer("🔍 Введите ключевое слово для поиска:")
    
@router.message(F.text & ~F.command())
async def process_search(message: types.Message):
    query = message.text
    lessons = await search_lessons_by_query(query)
    
    if not lessons:
        await message.answer("📭 По вашему запросу ничего не найдено")
        return
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=lesson.title, callback_data=f"lesson_{lesson.id}")]
            for lesson in lessons
        ]
    )
    
    await message.answer(f"🔍 Результаты поиска по запросу '{query}':", reply_markup=keyboard)
```

#### 7.2 Статистика использования
```python
@router.message(F.text == "📊 Статистика")
@admin_required
async def show_statistics(message: types.Message):
    stats = await get_usage_statistics()
    
    text = (
        "📊 Статистика использования бота:\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🆕 Новых пользователей сегодня: {stats['new_users_today']}\n"
        f"📚 Всего тем: {stats['total_themes']}\n"
        f"📖 Всего книг: {stats['total_books']}\n"
        f"🎧 Всего уроков: {stats['total_lessons']}\n"
        f"🎧 Прослушиваний сегодня: {stats['listens_today']}"
    )
    
    await message.answer(text)
```

### Этап 8: Тестирование и развертывание (2-3 дня)

#### 8.1 Написание тестов
```python
# tests/test_bot.py
async def test_start_command():
    # Тест команды /start
    pass

async def test_user_registration():
    # Тест регистрации пользователя
    pass

async def test_admin_access():
    # Тест доступа админа
    pass
```

#### 8.2 Подготовка к продакшену
- Настройка логирования
- Настройка мониторинга
- Создание инструкций по развертыванию
- Тестирование в Docker окружении

## Общие требования к коду

### Стиль кода
- Использование type hints
- Следование PEP 8
- Документация функций и классов
- Обработка ошибок

### Безопасность
- Валидация всех входных данных
- Проверка прав доступа
- Ограничение размера загружаемых файлов
- Защита от SQL инъекций

### Производительность
- Оптимизация запросов к БД
- Кэширование часто запрашиваемых данных
- Асинхронная обработка запросов

## Сроки реализации
- **Этап 1**: 1-2 дня
- **Этап 2**: 3-4 дня  
- **Этап 3**: 2-3 дня
- **Этап 4**: 3-4 дня
- **Этап 5**: 4-5 дней
- **Этап 6**: 3-4 дня
- **Этап 7**: 2-3 дня
- **Этап 8**: 2-3 дня

**Общий срок**: 20-28 дней (4-5 недель)

## Риски и митигация
1. **Проблемы с хранением аудио** - использовать облачное хранилище при необходимости
2. **Производительность БД** - оптимизация запросов, индексы
3. **Масштабирование** - подготовка к горизонтальному масштабированию
4. **Безопасность** - регулярные обновления зависимостей, аудит кода