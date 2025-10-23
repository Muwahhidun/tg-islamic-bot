# Спецификация мобильного приложения: Исламские аудио-уроки

## 📋 Общее описание

Мобильное приложение (iOS/Android) для прослушивания аудио-лекций по исламским наукам с системой тестирования знаний. Приложение использует существующую базу данных PostgreSQL от Telegram бота.

**Платформы:** iOS, Android (один код на Flutter)
**Backend:** FastAPI (Python) - новый REST API слой
**База данных:** PostgreSQL (общая с Telegram ботом)
**Аудио:** Стриминг MP3 файлов с сервера

---

## 🛠 Tech Stack

### Frontend (Mobile)
- **Flutter 3.x** - кросс-платформенный фреймворк
- **Dart 3.x** - язык программирования
- **Provider / Riverpod** - state management
- **just_audio** - аудио плеер с фоновым воспроизведением
- **audio_service** - фоновая работа аудио
- **dio** - HTTP клиент для API запросов
- **cached_network_image** - кэширование изображений
- **hive / sqflite** - локальное хранилище (оффлайн кэш)

### Backend (API)
- **FastAPI** - современный Python веб-фреймворк
- **SQLAlchemy 2.0** - ORM (использует существующие модели)
- **Pydantic** - валидация данных, serialization
- **asyncpg** - асинхронный драйвер PostgreSQL
- **Redis 7.x** - кэширование API ответов, сессии
- **aioredis / redis-py** - асинхронный клиент Redis
- **python-jose** - JWT токены для авторизации
- **passlib** - хэширование паролей (если нужна своя авторизация)

### Database
- **PostgreSQL 15** - существующая БД от Telegram бота
- **Shared schema** - приложение использует те же таблицы

### Caching
- **Redis 7.x** - in-memory кэш для быстродействия
- **Docker контейнер** - запускается вместе с PostgreSQL

---

## 🔴 Redis - Стратегия кэширования

### Зачем нужен Redis

**Проблема без кэша:**
```
Каждый запрос → PostgreSQL → 50-200ms
1000 пользователей → 1000 запросов к БД → перегрузка
```

**Решение с Redis:**
```
Первый запрос → PostgreSQL → сохраняем в Redis
Следующие запросы → Redis → 1-5ms (в 50 раз быстрее!)
```

### Что кэшировать

#### 1. **Список тем** (редко меняется)
```python
# FastAPI
from fastapi_cache.decorator import cache

@router.get("/themes")
@cache(expire=3600)  # 1 час
async def get_themes():
    return await crud.get_all_themes()
```

**Redis key:** `fastapi:themes:*`
**TTL:** 3600 секунд (1 час)
**Инвалидация:** При создании/удалении темы через админку

#### 2. **Список преподавателей**
```python
@router.get("/teachers")
@cache(expire=3600)  # 1 час
async def get_teachers():
    return await crud.get_all_teachers()
```

**Redis key:** `fastapi:teachers:*`
**TTL:** 3600 секунд

#### 3. **Серии преподавателя**
```python
@router.get("/teachers/{teacher_id}/series")
@cache(expire=1800)  # 30 минут
async def get_teacher_series(teacher_id: int):
    return await crud.get_series_by_teacher(teacher_id)
```

**Redis key:** `fastapi:teachers:{teacher_id}:series:*`
**TTL:** 1800 секунд (30 минут)

#### 4. **Уроки серии**
```python
@router.get("/series/{series_id}/lessons")
@cache(expire=1800)  # 30 минут
async def get_series_lessons(series_id: int):
    return await crud.get_lessons_by_series(series_id)
```

**Redis key:** `fastapi:series:{series_id}:lessons:*`
**TTL:** 1800 секунд

#### 5. **Детали урока**
```python
@router.get("/lessons/{lesson_id}")
@cache(expire=3600)  # 1 час
async def get_lesson(lesson_id: int):
    return await crud.get_lesson_by_id(lesson_id)
```

**Redis key:** `fastapi:lessons:{lesson_id}:*`
**TTL:** 3600 секунд

### Что НЕ кэшировать

❌ **Персональные данные пользователя** (закладки, попытки тестов)
❌ **Аудио файлы** (слишком большие, используй CDN)
❌ **JWT токены** (хранятся в отдельной Redis базе для сессий)

### Структура Redis

**2 базы данных:**

```python
# redis://localhost:6379/0 - Кэш API
REDIS_CACHE_DB = 0

# redis://localhost:6379/1 - Сессии/JWT
REDIS_SESSION_DB = 1
```

### Настройка в FastAPI

**requirements.txt:**
```txt
fastapi==0.104.0
redis==5.0.0
fastapi-cache2[redis]==0.2.1
```

**config.py:**
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/audio_bot"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_CACHE_DB: int = 0
    REDIS_SESSION_DB: int = 1
    REDIS_PASSWORD: str = ""

    # Кэш TTL (секунды)
    CACHE_TTL_THEMES: int = 3600      # 1 час
    CACHE_TTL_TEACHERS: int = 3600     # 1 час
    CACHE_TTL_SERIES: int = 1800       # 30 минут
    CACHE_TTL_LESSONS: int = 3600      # 1 час

    class Config:
        env_file = ".env"

settings = Settings()
```

**main.py:**
```python
from fastapi import FastAPI
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis

app = FastAPI(title="Islamic Audio Lessons API")

@app.on_event("startup")
async def startup():
    # Подключение к Redis для кэша
    redis = aioredis.from_url(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_CACHE_DB}",
        encoding="utf8",
        decode_responses=True
    )
    FastAPICache.init(RedisBackend(redis), prefix="fastapi:")
```

**Использование в эндпоинтах:**
```python
from fastapi_cache.decorator import cache

@router.get("/themes")
@cache(expire=settings.CACHE_TTL_THEMES)
async def get_themes(db: AsyncSession = Depends(get_db)):
    """
    Получить список тем.
    Кэшируется на 1 час.
    """
    themes = await crud.get_all_themes(db)
    return {"themes": themes}
```

### Инвалидация кэша (очистка)

Когда админ меняет данные через Telegram бота, нужно очистить кэш:

**Option 1: Очистка конкретных ключей**
```python
from fastapi_cache import FastAPICache

@router.post("/admin/themes", dependencies=[Depends(admin_required)])
async def create_theme(theme: ThemeCreate):
    # Создаём тему в БД
    new_theme = await crud.create_theme(theme)

    # Очищаем кэш тем
    await FastAPICache.clear(namespace="themes")

    return new_theme
```

**Option 2: Автоматическая очистка через Redis PubSub**
```python
# В Telegram боте при изменении данных:
import redis

r = redis.Redis(host='localhost', port=6379, db=0)

# При создании/изменении темы
r.publish('cache:invalidate', 'themes')

# При создании/изменении урока серии
r.publish('cache:invalidate', f'series:{series_id}:lessons')
```

```python
# В FastAPI слушаем канал
import asyncio

async def listen_cache_invalidation():
    pubsub = redis.pubsub()
    pubsub.subscribe('cache:invalidate')

    async for message in pubsub.listen():
        if message['type'] == 'message':
            namespace = message['data']
            await FastAPICache.clear(namespace=namespace)
```

### Docker Compose setup

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  # PostgreSQL (уже есть)
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: audio_bot
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  # Redis (НОВОЕ)
  redis:
    image: redis:7-alpine
    container_name: redis_cache
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

  # FastAPI Backend (НОВОЕ)
  api:
    build: ./backend
    container_name: fastapi_backend
    depends_on:
      - db
      - redis
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:${DB_PASSWORD}@db:5432/audio_bot
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_PASSWORD: ${REDIS_PASSWORD}
    volumes:
      - ./audio_files:/app/audio_files
    ports:
      - "8000:8000"
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  # Telegram Bot (уже есть)
  bot:
    build: .
    depends_on:
      - db
      - redis
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:${DB_PASSWORD}@db:5432/audio_bot
      REDIS_HOST: redis
      # ... остальные переменные

volumes:
  postgres_data:
  redis_data:
```

**.env:**
```env
# Database
DB_PASSWORD=your_secure_password

# Redis
REDIS_PASSWORD=your_redis_password

# API
JWT_SECRET=your_jwt_secret
```

### Мониторинг Redis

**Команды для проверки:**
```bash
# Подключиться к Redis
docker-compose exec redis redis-cli -a your_redis_password

# Посмотреть все ключи
KEYS fastapi:*

# Посмотреть конкретный ключ
GET fastapi:themes:hash

# Посмотреть TTL ключа
TTL fastapi:themes:hash

# Статистика Redis
INFO stats

# Очистить весь кэш (осторожно!)
FLUSHDB
```

### Оптимизация памяти

**Настройки Redis (redis.conf):**
```conf
# Максимум памяти (512 МБ для начала)
maxmemory 512mb

# Политика вытеснения (удалять старые ключи)
maxmemory-policy allkeys-lru

# Сжатие данных
list-compress-depth 1
```

### Производительность

**Без Redis:**
```
GET /lessons?series_id=5
PostgreSQL: 80-150ms
Пропускная способность: ~100 req/sec
```

**С Redis:**
```
GET /lessons?series_id=5
Redis hit: 2-5ms (первый раз 80ms + кэш)
Пропускная способность: ~5000 req/sec
```

**Результат:** API в **50 раз быстрее** для повторных запросов! 🚀

### Когда включать Redis

**MVP (первые 100 пользователей):** Можно без Redis
**Production (1000+ пользователей):** Redis обязателен

**Рекомендация:** Настрой Redis сразу, но включай кэширование постепенно:
1. Сначала тестируй без кэша
2. Потом добавь `@cache()` на самые популярные эндпоинты
3. Мониторь hit rate (Redis INFO)

---

## 🗄 Архитектура базы данных

База данных **ОБЩАЯ** с Telegram ботом. Все таблицы уже существуют.

### Таблицы (PostgreSQL)

#### 1. **roles** - Роли пользователей
```sql
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,  -- 'Admin', 'Moderator', 'User'
    description TEXT,
    level INTEGER NOT NULL DEFAULT 0,   -- 0=User, 1=Moderator, 2=Admin
    created_at TIMESTAMP NOT NULL
);
```

#### 2. **users** - Пользователи
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE,          -- NULL для мобильных пользователей
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    email VARCHAR(255) UNIQUE,          -- Для мобильного приложения
    password_hash VARCHAR(255),         -- Для мобильного приложения
    role_id INTEGER REFERENCES roles(id) DEFAULT 3,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

-- Индексы
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_email ON users(email);
```

**Важно:**
- Telegram пользователи: `telegram_id` заполнен, `email`/`password_hash` NULL
- Мобильные пользователи: `email`/`password_hash` заполнены, `telegram_id` NULL
- Можно связать аккаунты позже (один user_id для обеих платформ)

#### 3. **themes** - Темы (Акыда, Сира, Фикх, Адаб)
```sql
CREATE TABLE themes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,         -- 'Акыда', 'Сира', 'Фикх'
    desc TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_themes_is_active ON themes(is_active);
```

#### 4. **book_authors** - Авторы книг (классические учёные)
```sql
CREATE TABLE book_authors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,         -- 'Мухаммад ибн Абдуль-Ваххаб'
    biography TEXT,
    birth_year INTEGER,
    death_year INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_book_authors_is_active ON book_authors(is_active);
```

#### 5. **books** - Книги
```sql
CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    desc TEXT,
    theme_id INTEGER REFERENCES themes(id) ON DELETE SET NULL,
    author_id INTEGER REFERENCES book_authors(id) ON DELETE SET NULL,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_books_theme_id ON books(theme_id);
CREATE INDEX idx_books_author_id ON books(author_id);
CREATE INDEX idx_books_is_active ON books(is_active);
```

#### 6. **lesson_teachers** - Преподаватели (современные лекторы)
```sql
CREATE TABLE lesson_teachers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,         -- 'Мухаммад Абу Мунира'
    biography TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_lesson_teachers_is_active ON lesson_teachers(is_active);
```

#### 7. **lesson_series** - Серии уроков
```sql
CREATE TABLE lesson_series (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    year INTEGER NOT NULL,
    description TEXT,
    teacher_id INTEGER NOT NULL REFERENCES lesson_teachers(id) ON DELETE RESTRICT,
    book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
    theme_id INTEGER REFERENCES themes(id) ON DELETE SET NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    "order" INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    CONSTRAINT unique_series_per_teacher UNIQUE (year, name, teacher_id)
);

CREATE INDEX idx_lesson_series_name ON lesson_series(name);
CREATE INDEX idx_lesson_series_year ON lesson_series(year);
CREATE INDEX idx_lesson_series_teacher_id ON lesson_series(teacher_id);
CREATE INDEX idx_lesson_series_book_id ON lesson_series(book_id);
CREATE INDEX idx_lesson_series_theme_id ON lesson_series(theme_id);
CREATE INDEX idx_lesson_series_is_completed ON lesson_series(is_completed);
CREATE INDEX idx_lesson_series_is_active ON lesson_series(is_active);
```

#### 8. **lessons** - Уроки (главная таблица)
```sql
CREATE TABLE lessons (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,        -- Автогенерируется: teacher_book_year_series_урок_N
    description TEXT,
    audio_path VARCHAR(500),            -- Путь к MP3 файлу
    telegram_file_id VARCHAR(200),      -- Кэш для Telegram (не используется в mobile)
    lesson_number INTEGER,
    duration_seconds INTEGER,
    tags VARCHAR(500),                  -- Теги через запятую
    series_id INTEGER REFERENCES lesson_series(id) ON DELETE RESTRICT,
    book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
    teacher_id INTEGER REFERENCES lesson_teachers(id) ON DELETE SET NULL,
    theme_id INTEGER REFERENCES themes(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    CONSTRAINT unique_lesson_number_per_series UNIQUE (series_id, lesson_number)
);

CREATE INDEX idx_lessons_series_id ON lessons(series_id);
CREATE INDEX idx_lessons_book_id ON lessons(book_id);
CREATE INDEX idx_lessons_teacher_id ON lessons(teacher_id);
CREATE INDEX idx_lessons_theme_id ON lessons(theme_id);
CREATE INDEX idx_lessons_is_active ON lessons(is_active);
```

**Важно:**
- `title` автогенерируется при изменении метаданных
- `telegram_file_id` не используется в мобильном приложении
- В серии номера уроков уникальны

#### 9. **bookmarks** - Закладки пользователей
```sql
CREATE TABLE bookmarks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    custom_name VARCHAR(200) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT uq_user_lesson_bookmark UNIQUE (user_id, lesson_id)
);

CREATE INDEX idx_bookmarks_user_id ON bookmarks(user_id);
CREATE INDEX idx_bookmarks_lesson_id ON bookmarks(lesson_id);
```

**Лимит:** Максимум 20 закладок на пользователя (проверяется в приложении)

#### 10. **tests** - Тесты по сериям
```sql
CREATE TABLE tests (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    series_id INTEGER NOT NULL REFERENCES lesson_series(id) ON DELETE RESTRICT,
    teacher_id INTEGER NOT NULL REFERENCES lesson_teachers(id) ON DELETE RESTRICT,
    passing_score INTEGER DEFAULT 80,           -- Процент для прохождения
    time_per_question_seconds INTEGER DEFAULT 30,
    questions_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    "order" INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_tests_series_id ON tests(series_id);
CREATE INDEX idx_tests_teacher_id ON tests(teacher_id);
CREATE INDEX idx_tests_is_active ON tests(is_active);
```

#### 11. **test_questions** - Вопросы тестов
```sql
CREATE TABLE test_questions (
    id SERIAL PRIMARY KEY,
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    options JSON NOT NULL,              -- ["Ответ 1", "Ответ 2", "Ответ 3", "Ответ 4"]
    correct_answer_index INTEGER NOT NULL, -- 0-3
    explanation TEXT,
    "order" INTEGER DEFAULT 0,
    points INTEGER DEFAULT 1,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_test_questions_test_id ON test_questions(test_id);
CREATE INDEX idx_test_questions_lesson_id ON test_questions(lesson_id);
CREATE INDEX idx_test_questions_order ON test_questions("order");
```

#### 12. **test_attempts** - Попытки прохождения тестов
```sql
CREATE TABLE test_attempts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE SET NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,             -- NULL = не завершён
    score INTEGER DEFAULT 0,
    max_score INTEGER NOT NULL,
    passed BOOLEAN DEFAULT FALSE,
    answers JSON,                       -- {"question_1": 0, "question_2": 2, ...}
    time_spent_seconds INTEGER
);

CREATE INDEX idx_test_attempts_user_id ON test_attempts(user_id);
CREATE INDEX idx_test_attempts_test_id ON test_attempts(test_id);
CREATE INDEX idx_test_attempts_lesson_id ON test_attempts(lesson_id);
CREATE INDEX idx_test_attempts_passed ON test_attempts(passed);
```

#### 13. **feedbacks** - Обратная связь
```sql
CREATE TABLE feedbacks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message_text TEXT NOT NULL,
    admin_reply TEXT,
    status VARCHAR(20) DEFAULT 'new' NOT NULL, -- 'new', 'replied', 'closed'
    created_at TIMESTAMP NOT NULL,
    replied_at TIMESTAMP,
    closed_at TIMESTAMP
);

CREATE INDEX idx_feedbacks_user_id ON feedbacks(user_id);
CREATE INDEX idx_feedbacks_status ON feedbacks(status);
```

---

## 🔗 Связи и CASCADE правила

### Критически важные правила onDelete:

1. **Theme удалена** → books.theme_id, lesson_series.theme_id → `SET NULL`
2. **BookAuthor удалён** → books.author_id → `SET NULL`
3. **Book удалена** → lessons.book_id, lesson_series.book_id → `SET NULL`
4. **LessonTeacher удалён** → `RESTRICT` если есть series/tests
5. **LessonSeries удалена** → `RESTRICT` если есть lessons/tests ⚠️
6. **Lesson удалён** → `CASCADE` удаляет bookmarks, test_questions
7. **User удалён** → `CASCADE` удаляет все данные пользователя
8. **Test удалён** → `CASCADE` удаляет questions и attempts

**Важно:** Нельзя удалить серию если есть уроки или тесты!

---

## 🌐 FastAPI Backend Architecture

### Структура проекта
```
backend/
├── app/
│   ├── main.py                 # Точка входа FastAPI
│   ├── config.py               # Настройки (database URL, JWT secret)
│   ├── database.py             # SQLAlchemy setup
│   ├── models/                 # SQLAlchemy ORM модели
│   │   ├── user.py
│   │   ├── lesson.py
│   │   ├── test.py
│   │   └── ...
│   ├── schemas/                # Pydantic schemas (request/response)
│   │   ├── user.py
│   │   ├── lesson.py
│   │   ├── test.py
│   │   └── ...
│   ├── api/
│   │   ├── auth.py             # Авторизация (login, register, JWT)
│   │   ├── themes.py           # Темы
│   │   ├── teachers.py         # Преподаватели
│   │   ├── series.py           # Серии уроков
│   │   ├── lessons.py          # Уроки (список, детали, аудио стрим)
│   │   ├── bookmarks.py        # Закладки
│   │   ├── tests.py            # Тесты
│   │   └── feedbacks.py        # Обратная связь
│   ├── crud/                   # CRUD операции (database queries)
│   │   ├── user.py
│   │   ├── lesson.py
│   │   └── ...
│   ├── auth/                   # JWT, OAuth
│   │   ├── jwt.py
│   │   └── dependencies.py     # get_current_user
│   └── utils/
│       ├── audio.py            # Стриминг аудио
│       └── pagination.py
├── audio_files/                # Аудио файлы (общие с Telegram ботом)
├── requirements.txt
└── .env
```

### API Endpoints (REST)

#### Авторизация
```
POST   /api/auth/register          # Регистрация (email + password)
POST   /api/auth/login             # Вход (возвращает JWT token)
POST   /api/auth/refresh           # Обновить JWT token
GET    /api/auth/me                # Получить профиль текущего пользователя
```

#### Темы
```
GET    /api/themes                 # Список тем (с кол-вом книг/серий)
GET    /api/themes/{id}            # Детали темы
GET    /api/themes/{id}/books      # Книги темы
GET    /api/themes/{id}/series     # Серии темы
```

#### Авторы книг
```
GET    /api/authors                # Список авторов
GET    /api/authors/{id}           # Детали автора
GET    /api/authors/{id}/books     # Книги автора
```

#### Книги
```
GET    /api/books                  # Список книг (фильтр: theme_id, author_id)
GET    /api/books/{id}             # Детали книги
GET    /api/books/{id}/series      # Серии книги
```

#### Преподаватели
```
GET    /api/teachers               # Список преподавателей
GET    /api/teachers/{id}          # Детали преподавателя
GET    /api/teachers/{id}/series   # Серии преподавателя
```

#### Серии уроков
```
GET    /api/series                 # Список серий (фильтр: teacher_id, book_id, year)
GET    /api/series/{id}            # Детали серии
GET    /api/series/{id}/lessons    # Уроки серии
GET    /api/series/{id}/tests      # Тесты серии
```

#### Уроки
```
GET    /api/lessons                # Список уроков (пагинация, фильтры)
GET    /api/lessons/{id}           # Детали урока
GET    /api/lessons/{id}/audio     # Стрим аудио файла (range requests)
GET    /api/lessons/search         # Поиск уроков (query параметр)
```

#### Закладки
```
GET    /api/bookmarks              # Закладки текущего пользователя (max 20)
POST   /api/bookmarks              # Добавить закладку
DELETE /api/bookmarks/{id}         # Удалить закладку
```

#### Тесты
```
GET    /api/tests/{id}             # Детали теста
GET    /api/tests/{id}/questions   # Вопросы теста
POST   /api/tests/{id}/start       # Начать прохождение (создать attempt)
POST   /api/tests/attempts/{id}/answer  # Ответить на вопрос
POST   /api/tests/attempts/{id}/complete  # Завершить тест
GET    /api/tests/attempts/my      # История попыток пользователя
```

#### Обратная связь
```
GET    /api/feedbacks/my           # Мои обращения
POST   /api/feedbacks              # Отправить обращение
```

### Response примеры

**GET /api/lessons/{id}**
```json
{
  "id": 1,
  "title": "Мухаммад_Абу_Мунира_Три_основы_2025_Фаида_урок_1",
  "display_title": "Урок 1",
  "description": "Вступление в курс Три основы",
  "lesson_number": 1,
  "duration_seconds": 2258,
  "formatted_duration": "37м 38с",
  "audio_url": "/api/lessons/1/audio",
  "tags": ["акыда", "основы"],
  "series": {
    "id": 5,
    "name": "Фаида - 1",
    "year": 2025,
    "display_name": "2025 - Фаида - 1"
  },
  "teacher": {
    "id": 2,
    "name": "Мухаммад Абу Мунира"
  },
  "book": {
    "id": 3,
    "name": "Три основы"
  },
  "theme": {
    "id": 1,
    "name": "Акыда"
  },
  "is_active": true,
  "created_at": "2025-10-20T10:00:00"
}
```

**GET /api/series/{id}/lessons**
```json
{
  "series": {
    "id": 5,
    "name": "Фаида - 1",
    "year": 2025,
    "display_name": "2025 - Фаида - 1",
    "description": "Краткие пояснения к книге Три основы",
    "total_lessons": 8,
    "total_duration": "3ч 45м"
  },
  "lessons": [
    {
      "id": 1,
      "lesson_number": 1,
      "display_title": "Урок 1",
      "duration_seconds": 2258,
      "audio_url": "/api/lessons/1/audio"
    },
    ...
  ]
}
```

### Аудио стриминг

**GET /api/lessons/{id}/audio**

Поддержка:
- Range requests (для перемотки)
- Content-Length header
- Content-Type: audio/mpeg
- Accept-Ranges: bytes

```python
# FastAPI example
from fastapi import Response
from fastapi.responses import StreamingResponse

@router.get("/lessons/{lesson_id}/audio")
async def stream_audio(lesson_id: int, range: str = Header(None)):
    lesson = await get_lesson(lesson_id)
    file_path = lesson.audio_path

    # Range request support
    if range:
        # Parse range header, return partial content
        return StreamingResponse(file_stream, status_code=206, ...)

    return StreamingResponse(file_stream, media_type="audio/mpeg")
```

---

## 📱 Flutter Mobile App Architecture

### Структура проекта
```
mobile_app/
├── lib/
│   ├── main.dart
│   ├── config/
│   │   └── api_config.dart         # API base URL, endpoints
│   ├── models/                     # Data models (Dart classes)
│   │   ├── user.dart
│   │   ├── lesson.dart
│   │   ├── series.dart
│   │   ├── test.dart
│   │   └── ...
│   ├── services/                   # Business logic
│   │   ├── api_service.dart        # HTTP client (dio)
│   │   ├── auth_service.dart       # JWT, login/logout
│   │   ├── audio_service.dart      # Audio player
│   │   ├── cache_service.dart      # Local cache (Hive)
│   │   └── ...
│   ├── providers/                  # State management (Riverpod)
│   │   ├── auth_provider.dart
│   │   ├── lessons_provider.dart
│   │   ├── player_provider.dart
│   │   └── ...
│   ├── screens/                    # UI screens
│   │   ├── auth/
│   │   │   ├── login_screen.dart
│   │   │   └── register_screen.dart
│   │   ├── home/
│   │   │   └── home_screen.dart
│   │   ├── themes/
│   │   │   └── themes_list_screen.dart
│   │   ├── teachers/
│   │   │   ├── teachers_list_screen.dart
│   │   │   └── teacher_detail_screen.dart
│   │   ├── series/
│   │   │   └── series_detail_screen.dart
│   │   ├── lessons/
│   │   │   ├── lessons_list_screen.dart
│   │   │   └── lesson_detail_screen.dart
│   │   ├── player/
│   │   │   └── audio_player_screen.dart
│   │   ├── bookmarks/
│   │   │   └── bookmarks_screen.dart
│   │   ├── tests/
│   │   │   ├── test_detail_screen.dart
│   │   │   ├── test_question_screen.dart
│   │   │   └── test_result_screen.dart
│   │   └── profile/
│   │       └── profile_screen.dart
│   ├── widgets/                    # Reusable widgets
│   │   ├── lesson_card.dart
│   │   ├── series_card.dart
│   │   ├── audio_player_controls.dart
│   │   └── ...
│   └── utils/
│       ├── formatters.dart         # Duration, file size formatting
│       └── constants.dart
├── pubspec.yaml
└── assets/
    ├── images/
    └── fonts/
```

### Key Features

#### 1. Авторизация
- Email + password регистрация
- JWT token хранится в secure storage
- Auto-refresh token
- Logout

#### 2. Навигация
```
Главная
├─ 📚 По темам
│   └─ Тема → Книги → Серии → Уроки
├─ 👤 По преподавателям
│   └─ Преподаватель → Серии → Уроки
├─ 📖 По книгам
│   └─ Книга → Серии → Уроки
└─ 🔍 Поиск
```

#### 3. Аудио плеер
- Фоновое воспроизведение (audio_service)
- Управление с lock screen
- Seek bar (перемотка)
- Скорость воспроизведения (0.5x - 2x)
- Sleep timer
- Автопереход к следующему уроку в серии
- Кэширование для оффлайн режима (опционально)

#### 4. Закладки
- Максимум 20 на пользователя
- Быстрый доступ
- Переименование закладок

#### 5. Тесты
- Таймер на вопрос
- Сохранение прогресса
- Результаты с процентами
- История попыток
- Можно пересдавать

#### 6. Оффлайн режим
- Кэш метаданных (Hive)
- Скачанные аудио (опционально)
- Синхронизация при подключении

---

## 🔐 Авторизация и безопасность

### JWT Tokens
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**Access token:** 1 час
**Refresh token:** 7 дней

### Headers
```
Authorization: Bearer {access_token}
```

### Регистрация
```json
POST /api/auth/register
{
  "email": "user@example.com",
  "password": "secure_password",
  "first_name": "Имя",
  "last_name": "Фамилия"
}
```

### Вход
```json
POST /api/auth/login
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

---

## 🎨 UI/UX Дизайн

### Цветовая схема
- **Primary:** Зелёный (#2E7D32) - исламская тематика
- **Secondary:** Золотой (#FFC107)
- **Background:** Белый / Тёмный режим
- **Text:** Чёрный / Белый

### Шрифты
- **Основной:** Roboto / SF Pro (системный)
- **Арабский:** Noto Naskh Arabic (для арабских текстов)

### Компоненты
- Bottom Navigation Bar (Главная, Поиск, Закладки, Профиль)
- Карточки уроков с длительностью
- Аудио плеер с waveform visualization
- Progress indicators для тестов

---

## 📊 Метрики и аналитика

### Что отслеживать:
- Количество прослушанных уроков (user_id, lesson_id, timestamp)
- Время прослушивания (в секундах)
- Пройденные тесты (score, attempts)
- Популярные преподаватели/серии
- Конверсия регистрации

### Новая таблица (опционально):
```sql
CREATE TABLE listening_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE CASCADE,
    listened_seconds INTEGER,
    completed BOOLEAN DEFAULT FALSE,
    listened_at TIMESTAMP NOT NULL
);
```

---

## 🚀 Deployment

### Backend (FastAPI)
- **Сервер:** DigitalOcean / AWS / Heroku
- **WSGI:** Uvicorn + Gunicorn
- **Reverse proxy:** Nginx
- **SSL:** Let's Encrypt
- **Database:** PostgreSQL (та же, что у бота)

### Frontend (Flutter)
- **iOS:** App Store (требует Apple Developer Account $99/год)
- **Android:** Google Play Store ($25 единоразово)

### Общие ресурсы
- **База данных:** Общая PostgreSQL
- **Аудио файлы:** Общая папка `audio_files/`
- **Можно разделить домены:**
  - bot.example.com - Telegram бот
  - api.example.com - FastAPI
  - example.com - будущий веб-сайт

---

## 🔄 Интеграция с Telegram ботом

### Что общего:
✅ База данных PostgreSQL
✅ Аудио файлы
✅ Пользовательские данные (если связать аккаунты)

### Что раздельно:
❌ Авторизация (Telegram = telegram_id, Mobile = email/password)
❌ File caching (telegram_file_id не используется в mobile)
❌ Обработчики (бот = aiogram, mobile = FastAPI)

### Миграция пользователей:
Можно добавить связь аккаунтов:
1. Пользователь вошёл в бота через Telegram
2. В боте появляется опция "Связать с мобильным приложением"
3. Генерируется код
4. Код вводится в мобильном приложении
5. Обновляется user: telegram_id + email заполнены
6. Общие закладки, история, тесты

---

## ✅ Чек-лист разработки

### Backend (FastAPI)
- [ ] Настроить FastAPI проект
- [ ] Подключить PostgreSQL (использовать существующие модели)
- [ ] Создать Pydantic schemas
- [ ] Реализовать JWT авторизацию
- [ ] API endpoints для тем, книг, преподавателей
- [ ] API endpoints для серий и уроков
- [ ] Аудио стриминг с Range requests
- [ ] API для тестов
- [ ] API для закладок
- [ ] Обратная связь
- [ ] Пагинация и фильтрация
- [ ] Документация (Swagger автоматом)
- [ ] Deploy на сервер

### Frontend (Flutter)
- [ ] Setup Flutter проект
- [ ] State management (Riverpod)
- [ ] API integration (dio)
- [ ] Авторизация (JWT)
- [ ] Навигация (bottom nav bar)
- [ ] Экраны: темы, преподаватели, книги
- [ ] Список уроков
- [ ] Аудио плеер (just_audio)
- [ ] Фоновое воспроизведение (audio_service)
- [ ] Закладки
- [ ] Тесты (вопросы, таймер, результаты)
- [ ] Профиль пользователя
- [ ] Оффлайн кэш (Hive)
- [ ] Поиск
- [ ] Тёмная тема
- [ ] Локализация (русский, арабский)
- [ ] Тестирование
- [ ] Build iOS/Android
- [ ] Deploy в App Store / Google Play

---

## 📚 Полезные ссылки

### FastAPI
- Документация: https://fastapi.tiangolo.com/
- SQLAlchemy 2.0: https://docs.sqlalchemy.org/
- Pydantic: https://docs.pydantic.dev/

### Flutter
- Документация: https://docs.flutter.dev/
- just_audio: https://pub.dev/packages/just_audio
- audio_service: https://pub.dev/packages/audio_service
- riverpod: https://riverpod.dev/
- dio: https://pub.dev/packages/dio

### Design
- Material Design: https://m3.material.io/
- Islamic UI patterns: https://dribbble.com/tags/islamic_app

---

## 💡 Дополнительные фичи (MVP+)

1. **Социальные функции**
   - Комментарии к урокам
   - Рейтинг уроков
   - Поделиться уроком

2. **Прогресс обучения**
   - Трекинг прослушанных уроков
   - Сертификаты по завершению серий
   - Статистика (часов прослушано, тестов пройдено)

3. **Уведомления**
   - Push при новых уроках любимого преподавателя
   - Напоминания продолжить прослушивание

4. **Монетизация**
   - Премиум подписка (эксклюзивные уроки)
   - Донаты преподавателям

5. **Улучшения аудио**
   - Эквалайзер
   - Шумоподавление
   - Скачивание для оффлайн

---

## 🎯 MVP (Minimal Viable Product)

**Приоритет 1 (must have):**
- Регистрация/Вход
- Просмотр тем, преподавателей, серий
- Список уроков
- Аудио плеер с фоном
- Закладки
- Базовый поиск

**Приоритет 2 (should have):**
- Тесты
- История прослушивания
- Обратная связь

**Приоритет 3 (nice to have):**
- Оффлайн режим
- Социальные функции
- Статистика

---

**Этот документ - полная спецификация для начала разработки мобильного приложения. Используй его как референс при написании кода и промптов для AI ассистента.**
