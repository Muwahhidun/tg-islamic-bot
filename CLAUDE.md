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
├── handlers/          # Telegram command handlers (user.py, admin.py)
├── keyboards/         # Inline and reply keyboards
├── models/           # SQLAlchemy models (database.py, user.py, theme.py, book.py, lesson.py, etc.)
├── services/         # Business logic (database_service.py)
├── utils/            # Config, decorators, audio utilities
└── main.py           # Entry point - registers routers and starts polling
```

### Database Schema

**Key tables**:
- `users` → `roles` (admin/moderator/user with level-based permissions)
- `themes` (Акыда, Сира, Фикх, Адаб)
- `books` → `book_authors` (classical scholars)
- `lessons` → `lesson_teachers` (modern lecturers)

**Critical relationships**:
- `books.theme_id` → `themes.id`
- `books.author_id` → `book_authors.id`
- `lessons.book_id` → `books.id`
- `lessons.teacher_id` → `lesson_teachers.id`

**Indexes**: Full-text search on lessons (Russian language), composite indexes on `(book_id, lesson_number)`, and standard indexes on foreign keys.

### SQLAlchemy Usage

- All DB operations use **async/await** with `async_session_maker`
- Models inherit from `Base` ([bot/models/database.py](bot/models/database.py))
- Database URL constructed in [bot/utils/config.py](bot/utils/config.py) from environment variables
- Tables are auto-created on startup via `create_tables()` in [bot/main.py](bot/main.py)

### Handler Registration

Handlers are organized in routers:
- [bot/handlers/user.py](bot/handlers/user.py) - User-facing commands (start, themes, lessons)
- [bot/handlers/admin.py](bot/handlers/admin.py) - Admin/moderator commands

Routers are included in the dispatcher in [bot/main.py](bot/main.py):
```python
dp.include_router(user.router)
dp.include_router(admin.router)
```

### Role-Based Access Control

Access control decorators in [bot/utils/decorators.py](bot/utils/decorators.py):
- `@admin_required` - Requires `role.level >= 2`
- `@moderator_required` - Requires `role.level >= 1`

Role levels:
- Admin (level 2) - Full system access
- Moderator (level 1) - Manage lessons and teachers
- User (level 0) - Browse and listen to content

## Configuration

Environment variables in `.env`:
- `BOT_TOKEN` - Telegram bot token from @BotFather
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - PostgreSQL connection
- `ADMIN_TELEGRAM_ID` - Initial admin user ID
- `DEBUG`, `LOG_LEVEL` - Logging configuration
- `MAX_AUDIO_SIZE_MB`, `ALLOWED_AUDIO_FORMATS` - Audio file constraints

Config is loaded via pydantic-settings in [bot/utils/config.py](bot/utils/config.py).

## Audio File Handling

- Audio files stored in `bot/audio_files/` (mounted as Docker volume)
- Supported formats: mp3, wav, ogg, m4a
- Duration extraction uses `mutagen` library
- Files uploaded via Telegram are downloaded to local storage and paths saved in `lessons.audio_path`

## Testing and Development Workflow

1. Make code changes in `bot/` directory
2. Restart bot container: `docker-compose restart bot`
3. Check logs: `docker-compose logs -f bot`
4. Access Adminer (database UI) at http://localhost:8080 (server: db, user/db: postgres/audio_bot)

## Initial Data

The project includes test data ([init_data.py](init_data.py)) with:
- 4 themes (Акыда, Сира, Фикх, Адаб)
- 3 book authors (classical scholars)
- 3 lesson teachers (modern lecturers)
- 3 books ("4 правила", "Три основа", "Жизнь пророка ﷺ")
- 12 sample lessons with tags and numbering

## Database Migrations

This project uses Alembic for migrations:

```bash
# Initialize Alembic (already done)
docker-compose exec bot alembic init alembic

# Generate migration from model changes
docker-compose exec bot alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec bot alembic upgrade head
```

## Code Style

- Async/await for all I/O operations
- Type hints encouraged
- Docstrings for modules and complex functions
- PEP 8 formatting
- Russian language for UI messages and comments

## Common Tasks

### Adding a new handler
1. Add function to [bot/handlers/user.py](bot/handlers/user.py) or [bot/handlers/admin.py](bot/handlers/admin.py)
2. Decorate with `@router.message()` or `@router.callback_query()`
3. Apply role decorators if needed (`@admin_required`, `@moderator_required`)
4. Restart bot: `docker-compose restart bot`

### Adding a new model
1. Create model class in `bot/models/` inheriting from `Base`
2. Define columns with SQLAlchemy types
3. Restart bot (tables auto-create on startup)
4. For production, generate Alembic migration instead

### Modifying database schema
1. Edit model in `bot/models/`
2. Generate migration: `docker-compose exec bot alembic revision --autogenerate -m "change description"`
3. Review migration in `alembic/versions/`
4. Apply: `docker-compose exec bot alembic upgrade head`

## Troubleshooting

**Bot not starting**: Check logs with `docker-compose logs bot`. Common issues:
- Missing `BOT_TOKEN` in `.env`
- Database connection failure (check `DB_*` variables)

**Database connection errors**: Ensure `DB_HOST=db` (not localhost) in `.env` when running in Docker.

**Permission denied on audio files**: Run `chmod 755 bot/audio_files` on host.

**Test data not loading**: Run `python init_data.py` after containers are up, or use `./run.sh` which handles this automatically.
