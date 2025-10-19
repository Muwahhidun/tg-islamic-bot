# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Islamic audio lessons Telegram bot built with Python, aiogram 3.x, PostgreSQL, and Docker. The bot organizes Islamic educational content hierarchically: Themes → Books → Lessons. It supports audio playback, search, and role-based access control (Admin, Moderator, User).

**Key concept**: The project separates **book authors** (classical Islamic scholars like Мухаммад ибн Абдуль-Ваххаб) from **lesson teachers** (modern lecturers who narrate the lessons like Мухаммад Абу Мунира).

## Technology Stack

- **Language**: Python 3.11+
- **Bot Framework**: aiogram 3.4.1
- **Database**: PostgreSQL 15
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Containerization**: Docker + Docker Compose

## Development Commands

### Local Development

```bash
# Start the entire stack (bot + database + adminer)
docker-compose up -d --build

# View bot logs in real-time
docker-compose logs -f bot

# Restart just the bot after code changes
docker-compose restart bot

# Stop all services
docker-compose down

# Complete reset (removes volumes/data)
docker-compose down -v && ./run.sh
```

### Database Operations

```bash
# Connect to PostgreSQL
docker-compose exec db psql -U postgres -d audio_bot

# Create a database backup
docker-compose exec db pg_dump -U postgres audio_bot > backup.sql

# Restore from backup
docker-compose exec -T db psql -U postgres audio_bot < backup.sql

# Make a user an admin (replace TELEGRAM_ID with actual ID from @userinfobot)
docker-compose exec db psql -U postgres -d audio_bot -c "UPDATE users SET role_id = 1 WHERE telegram_id = TELEGRAM_ID;"
```

### Initial Setup

```bash
# Quick start script (creates dirs, initializes DB, starts containers)
./run.sh

# Manual setup:
cp .env.example .env
# Edit .env with your BOT_TOKEN and credentials
docker-compose up -d --build
python init_data.py  # Populate test data
```

## Project Architecture

### Directory Structure

```
bot/
├── handlers/
│   ├── admin/           # Admin handlers (modular: themes.py, authors.py, books.py, etc.)
│   │   └── __init__.py  # Includes all admin sub-routers
│   └── user/            # User handlers (modular: themes.py, lessons.py, search.py)
│       └── __init__.py  # Includes all user sub-routers
├── keyboards/           # Inline and reply keyboards (user.py)
├── models/              # SQLAlchemy models
│   ├── database.py      # Base, engine, async_session_maker
│   ├── user.py, role.py
│   ├── theme.py, book.py, lesson.py
│   └── book_author.py, lesson_teacher.py
├── services/
│   └── database_service.py  # All DB operations (UserService, ThemeService, etc.)
├── utils/
│   ├── config.py        # Pydantic settings from .env
│   ├── decorators.py    # @admin_required, @moderator_required
│   └── audio_utils.py   # Audio file handling utilities
└── main.py              # Entry point - creates tables, registers routers, starts polling
```

### Handler Organization

**Modular structure**: Admin and user handlers are split into separate files by domain:
- [bot/handlers/admin/__init__.py](bot/handlers/admin/__init__.py) - Main admin router that includes all sub-routers (themes, authors, books, lessons, teachers, users, stats)
- [bot/handlers/user/__init__.py](bot/handlers/user/__init__.py) - Main user router that includes themes, lessons, search

**Router registration flow**:
1. Domain routers (e.g., `themes.router`, `books.router`) defined in their respective files
2. Included in parent routers ([bot/handlers/admin/__init__.py](bot/handlers/admin/__init__.py), [bot/handlers/user/__init__.py](bot/handlers/user/__init__.py))
3. Parent routers included in dispatcher in [bot/main.py](bot/main.py)

### Database Schema

**Key models and relationships**:
- `users` → `roles` (FK: `user.role_id`)
- `themes` (1) → (N) `books` (FK: `book.theme_id`, **ON DELETE SET NULL**)
- `books` (1) → (N) `lessons` (FK: `lesson.book_id`, **ON DELETE CASCADE**)
- `book_authors` (1) → (N) `books` (FK: `book.author_id`, **ON DELETE SET NULL**)
- `lesson_teachers` (1) → (N) `lessons` (FK: `lesson.teacher_id`, **ON DELETE SET NULL**)

**IMPORTANT deletion behavior**:
- Deleting a **theme** does NOT delete books - books get `theme_id = NULL`
- Deleting an **author** does NOT delete books - books get `author_id = NULL`
- Deleting a **teacher** does NOT delete lessons - lessons get `teacher_id = NULL`
- Deleting a **book** DOES delete all its lessons (CASCADE)

**Indexes**: Full-text search on lessons (Russian language), composite indexes on `(book_id, lesson_number)`, standard indexes on all foreign keys.

### Database Service Layer

All database operations go through [bot/services/database_service.py](bot/services/database_service.py):

**Service classes**:
- `UserService` - User CRUD, get_or_create_user, update_role
- `ThemeService` - Not explicitly defined, uses module-level functions
- Module-level functions like `get_all_books()`, `create_book()`, `update_book()`, `delete_book()`

**IMPORTANT patterns**:
- Always use `async with async_session_maker() as session:` for DB operations
- Use `joinedload()` for eager loading relationships to avoid DetachedInstanceError:
  ```python
  select(Book).options(
      joinedload(Book.author),
      joinedload(Book.theme),
      joinedload(Book.lessons)
  )
  ```
- Use `.unique().scalar_one_or_none()` when using joinedload to avoid duplicate rows

### Role-Based Access Control

Decorators in [bot/utils/decorators.py](bot/utils/decorators.py):
- `@admin_required` - Requires `role.level >= 2`
- `@moderator_required` - Requires `role.level >= 1`
- Helper: `is_user_admin(telegram_id)` - Returns boolean

**Role levels**:
- Admin (level 2, role_id=1) - Full system access
- Moderator (level 1, role_id=2) - Manage lessons and teachers
- User (level 0, role_id=3) - Browse and listen to content

### FSM (Finite State Machine)

Used for multi-step interactions like creating/editing entities:

```python
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

class BookStates(StatesGroup):
    name = State()
    description = State()
    theme_id = State()
    author_id = State()

# In handler:
await state.set_state(BookStates.name)
await state.update_data(book_id=book_id)  # Store context
data = await state.get_data()  # Retrieve context
await state.clear()  # Reset state
```

**Pattern for create vs. edit**:
- Store `book_id` (or similar) in state data for editing
- Check `if "book_id" in data:` to determine if editing or creating
- Same message handler can serve both create and edit flows

## Configuration

Environment variables in `.env`:
- `BOT_TOKEN` - Telegram bot token from @BotFather
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - PostgreSQL connection
- `ADMIN_TELEGRAM_ID` - Initial admin user ID
- `DEBUG`, `LOG_LEVEL` - Logging configuration
- `MAX_AUDIO_SIZE_MB`, `ALLOWED_AUDIO_FORMATS` - Audio file constraints

Config loaded via pydantic-settings in [bot/utils/config.py](bot/utils/config.py).

## Audio File Handling

- Audio files stored in `bot/audio_files/` (mounted as Docker volume)
- Supported formats: mp3, wav, ogg, m4a
- Duration extraction uses `mutagen` library
- Files uploaded via Telegram are downloaded to local storage and paths saved in `lessons.audio_path`

## Common Development Patterns

### Adding a new CRUD entity

1. **Create model** in `bot/models/yourmodel.py`:
   ```python
   from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
   from sqlalchemy.orm import relationship
   from .database import Base

   class YourModel(Base):
       __tablename__ = "your_table"
       id = Column(Integer, primary_key=True, index=True)
       name = Column(String(255), nullable=False)
       # ... other fields
   ```

2. **Add service functions** in [bot/services/database_service.py](bot/services/database_service.py):
   ```python
   async def get_all_yourmodels() -> List[YourModel]:
       async with async_session_maker() as session:
           result = await session.execute(select(YourModel))
           return result.scalars().all()

   async def create_yourmodel(name: str, ...) -> YourModel:
       async with async_session_maker() as session:
           obj = YourModel(name=name, ...)
           session.add(obj)
           await session.commit()
           await session.refresh(obj)
           return obj
   ```

3. **Create handlers** in `bot/handlers/admin/yourmodels.py`:
   ```python
   from aiogram import Router, F
   from aiogram.types import CallbackQuery, Message
   from bot.utils.decorators import admin_required

   router = Router()

   @router.callback_query(F.data == "admin_yourmodels")
   @admin_required
   async def admin_yourmodels(callback: CallbackQuery):
       # List view
       pass

   @router.callback_query(F.data.startswith("edit_yourmodel_"))
   @admin_required
   async def edit_yourmodel_menu(callback: CallbackQuery):
       # Edit menu
       pass
   ```

4. **Include router** in [bot/handlers/admin/__init__.py](bot/handlers/admin/__init__.py):
   ```python
   from . import yourmodels
   router.include_router(yourmodels.router)
   ```

5. **Restart bot**: `docker-compose restart bot`

### Callback Query Filter Patterns

```python
# Exact match
@router.callback_query(F.data == "admin_books")

# Regex match (preferred for numeric IDs)
@router.callback_query(F.data.regexp(r"^edit_book_\d+$"))

# startswith (use with manual validation)
@router.callback_query(F.data.startswith("edit_book_"))
async def handler(callback: CallbackQuery):
    # Validate inside function to avoid catching edit_book_name_, etc.
    parts = callback.data.split("_")
    if len(parts) != 3 or not parts[2].isdigit():
        return  # Not our pattern, skip
    book_id = int(parts[2])
    # ... handler logic
```

**Handler order matters**: More specific handlers must be registered BEFORE generic ones. In files, place specific handlers (like `edit_book_name_`) BEFORE generic handlers (like `edit_book_`).

### Inline Keyboard Patterns

```python
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

builder = InlineKeyboardBuilder()
for item in items:
    builder.add(InlineKeyboardButton(
        text=f"✅ {item.name}" if item.is_active else f"❌ {item.name}",
        callback_data=f"edit_item_{item.id}"
    ))
builder.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
builder.adjust(1)  # 1 button per row

await message.edit_text("Select item:", reply_markup=builder.as_markup())
```

## Debugging

### Viewing Logs

```bash
# Real-time logs
docker-compose logs -f bot

# Last 50 lines
docker-compose logs --tail=50 bot

# Search logs
docker-compose logs bot | grep "ERROR"
```

### Common Issues

**"Update is not handled" with short duration (13-16ms)**:
- These callbacks are filtered by aiogram BEFORE reaching handlers
- Usually caused by stale inline keyboard buttons from previously edited messages
- **Fix**: Ask user to close/reopen Telegram app to clear cache, or navigate fresh to the admin panel

**DetachedInstanceError**:
- Accessing relationships outside of session scope
- **Fix**: Use `joinedload()` when querying:
  ```python
  select(Book).options(joinedload(Book.author), joinedload(Book.theme))
  ```

**Handler not triggering**:
- Check handler order (specific before generic)
- Check filter syntax (use `F.data.regexp(r"^pattern$")` for exact patterns)
- Add debug logging at ERROR level to make logs stand out:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  logger.error(f"✅ Handler triggered for {callback.data}")
  ```

**Database connection errors**:
- Ensure `DB_HOST=db` (not localhost) in `.env` when running in Docker
- Check if database container is running: `docker-compose ps`

## Testing and Development Workflow

1. Make code changes in `bot/` directory
2. Restart bot container: `docker-compose restart bot`
3. Check logs: `docker-compose logs -f bot`
4. Test in Telegram by sending commands to your bot
5. Access Adminer (database UI) at http://localhost:8080
   - Server: `db`
   - Username: `postgres`
   - Password: from `.env` (`DB_PASSWORD`)
   - Database: `audio_bot`

## Initial Data

The project includes test data ([init_data.py](init_data.py)) with:
- 4 themes (Акыда, Сира, Фикх, Адаб)
- 3 book authors (classical scholars)
- 3 lesson teachers (modern lecturers)
- 3 books ("4 правила", "Три основа", "Жизнь пророка ﷺ")
- 12 sample lessons with tags and numbering

**IMPORTANT**: Lesson duration is stored in **seconds** (`duration_seconds`), not minutes.

## Code Style and Conventions

- **Async/await** for all I/O operations
- Type hints encouraged: `async def get_user(user_id: int) -> Optional[User]:`
- Docstrings for modules and complex functions
- PEP 8 formatting
- **Russian language** for all UI messages, comments, and user-facing text
- **English** for code (variable names, function names, class names)

## Key Reminders

1. **Always eager load relationships** with `joinedload()` to avoid DetachedInstanceError
2. **Check handler order** - specific patterns before generic patterns
3. **Use database_service.py** for all DB operations - don't write raw SQL in handlers
4. **Test with docker-compose restart bot** after every code change
5. **Deletion cascades**: Only books → lessons cascade. Themes/authors/teachers use SET NULL
6. **Dual-purpose handlers**: Use FSM state data to differentiate create vs. edit flows
7. **Debug unhandled callbacks**: Short duration (13-16ms) indicates aiogram filtering before handlers - likely stale Telegram cache
