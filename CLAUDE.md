# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Islamic Audio Lessons Telegram Bot - Platform for organizing and streaming audio lessons on Islamic sciences with hierarchical content structure: Themes → Books → Series → Lessons.

**Tech Stack:**
- Python 3.11+ with aiogram 3.x (Telegram bot framework)
- PostgreSQL 15 (primary database)
- SQLAlchemy 2.0 (async ORM)
- Docker + Docker Compose (containerization)
- Alembic (database migrations)

**Language:** All user-facing text, comments, and commit messages in Russian (Cyrillic).

**Key Concept:** Separation between **book authors** (classical Islamic scholars like Мухаммад ибн Абдуль-Ваххаб) and **lesson teachers** (modern instructors like Мухаммад Абу Мунира).

## Development Commands

### Docker Operations
```bash
# Start all services
docker-compose up -d

# Restart bot after code changes
docker-compose restart bot

# View bot logs (real-time)
docker-compose logs bot --tail=20 --follow

# Execute commands inside bot container
docker-compose exec bot python <script.py>

# Stop all services
docker-compose down

# Rebuild after dependency changes
docker-compose up -d --build

# Reset database (WARNING: destroys all data)
docker-compose down -v
docker-compose up -d
```

### Database Operations
```bash
# Access PostgreSQL CLI
docker-compose exec db psql -U postgres -d audio_bot

# Access Adminer web interface at http://localhost:8080
# Server: db, User: postgres, Password: from .env

# Create migration
docker-compose exec bot alembic revision --autogenerate -m "Description"

# Apply migrations
docker-compose exec bot alembic upgrade head

# Make user admin (replace TELEGRAM_ID)
docker-compose exec db psql -U postgres -d audio_bot -c "UPDATE users SET role_id = 1 WHERE telegram_id = TELEGRAM_ID;"
```

## Architecture

### Data Model Hierarchy

**Current Structure (normalized):**
```
Theme (Акыда, Сира, Фикх, Адаб)
  └── Book (has optional BookAuthor and Theme)
      └── LessonSeries (year + name, belongs to Teacher, optional Book/Theme)
          └── Lesson (series_id FK, audio file, number, title, description, tags)
              └── Test (optional, linked to Series)

User Features:
  └── Bookmark (user saves lesson with custom name, max 20 per user)
  └── Feedback (3-status workflow: new → replied → closed)
```

**CRITICAL: Series Migration**
- ✅ All lessons MUST have valid `series_id` (FK to `lesson_series`)
- ❌ Fields `series_year` and `series_name` have been REMOVED from Lesson model
- ⚠️ Never query or reference `lesson.series_year` or `lesson.series_name`
- ✅ Use `lesson.series.year` and `lesson.series.name` through relationship

**Important Distinctions:**
- `BookAuthor` - Classical scholars (e.g., Muhammad ibn Abd al-Wahhab)
- `LessonTeacher` - Modern instructors who deliver lessons
- `LessonSeries` - Groups lessons by teacher, year, and topic/book

**CASCADE/RESTRICT Rules (onDelete behavior):**

When deleting entities:
- **Theme** deleted → books.theme_id, lesson_series.theme_id → SET NULL (books/series remain)
- **BookAuthor** deleted → books.author_id → SET NULL (books remain)
- **Book** deleted → lessons.book_id, lesson_series.book_id → SET NULL (lessons/series remain)
- **LessonTeacher** deleted → RESTRICT if has series/tests, otherwise lessons.teacher_id → SET NULL
- **LessonSeries** deleted → **RESTRICT** if has lessons/tests (cannot delete series with content)
- **Lesson** deleted → CASCADE deletes bookmarks, test_questions; test_attempts.lesson_id → SET NULL
- **User** deleted → CASCADE deletes all user data (bookmarks, test_attempts, feedbacks)
- **Test** deleted → CASCADE deletes all test_questions and test_attempts

**Critical:** Cannot delete LessonSeries if it has lessons or tests attached. Must delete/move lessons first.

### Handler Architecture

**Two-tier system:**
1. **User handlers** (`bot/handlers/user/`) - Public interface
   - `themes.py` - Browse themes
   - `lessons.py` - Playback and navigation
   - `search.py` - Search functionality
   - `bookmarks.py` - User bookmarks management (max 20 per user)
   - `feedback.py` - User feedback submission
   - `teachers.py` - Browse lessons by teacher
   - `series.py` - Browse lessons by series
   - `tests.py` - Testing functionality

2. **Admin handlers** (`bot/handlers/admin/`) - Management interface
   - Entity CRUD: `themes.py`, `authors.py`, `books.py`, `teachers.py`, `series.py`
   - `lessons.py` - Lesson management with audio upload
   - `users.py` - User and role management
   - `tests.py` - Test and question management
   - `feedbacks.py` - Feedback management (3-status workflow)
   - `stats.py` - Platform statistics

**Single-Window UX Pattern (CRITICAL):**

All admin CRUD operations use single-window editing:

```python
# Pattern 1: Edit handlers
@router.callback_query(F.data.startswith("edit_theme_name_"))
async def edit_theme_name_start(callback: CallbackQuery, state: FSMContext):
    theme_id = int(callback.data.split("_")[3])
    # Save message coordinates for later update
    await state.update_data(
        theme_id=theme_id,
        edit_message_id=callback.message.message_id,
        edit_chat_id=callback.message.chat.id
    )
    await state.set_state(ThemeStates.name)
    # ... prompt for input

# Pattern 2: Save handlers
@router.message(ThemeStates.name)
async def save_theme_name(message: Message, state: FSMContext):
    data = await state.get_data()
    theme_id = data.get("theme_id")

    if theme_id:  # EDITING
        # Delete user input message
        try:
            await message.delete()
        except:
            pass

        # Update entity
        theme = await get_theme_by_id(theme_id)
        theme.name = message.text
        await update_theme(theme)

        # Reload to get fresh data
        theme = await get_theme_by_id(theme_id)

        # Build complete edit menu
        info = f"📚 <b>{theme.name}</b>\n..."
        builder = InlineKeyboardBuilder()
        # ... add all edit buttons

        # Update ORIGINAL message
        await message.bot.edit_message_text(
            chat_id=data['edit_chat_id'],
            message_id=data['edit_message_id'],
            text=info,
            reply_markup=builder.as_markup()
        )
        await state.clear()
    else:  # CREATING
        # Continue creation flow
        await state.update_data(name=message.text)
        # ... next step

# Pattern 3: Creation completion
async def complete_creation(message: Message, state: FSMContext):
    data = await state.get_data()

    # Delete user input
    try:
        await message.delete()
    except:
        pass

    # Create entity
    theme = await create_theme(name=data['name'], ...)

    # Load all entities
    themes = await get_all_themes()

    # Build list view
    builder = InlineKeyboardBuilder()
    for theme in themes:
        builder.add(...)

    # Update ORIGINAL message to show list
    await message.bot.edit_message_text(
        chat_id=data['create_chat_id'],
        message_id=data['create_message_id'],
        text="📚 <b>Управление темами</b>",
        reply_markup=builder.as_markup()
    )
    await state.clear()
```

**Validation Errors (Single Window):**
```python
# Check for duplicate name
existing = await get_theme_by_name(new_name)
if existing and existing.id != theme_id:
    try:
        await message.delete()
    except:
        pass

    # Show error in SAME window
    await message.bot.edit_message_text(
        chat_id=data['edit_chat_id'],
        message_id=data['edit_message_id'],
        text="❌ <b>Ошибка!</b>\n\nТема с таким названием уже существует!\n\nВведите другое название:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Отмена", callback_data=f"edit_theme_{theme_id}")
        ]])
    )
    # DON'T clear state - user can retry
    return
```

### Database Service Layer

`bot/services/database_service.py` provides all CRUD operations.

**Critical Patterns:**

1. **Eager Loading (avoid N+1 and DetachedInstanceError):**
```python
result = await session.execute(
    select(Lesson)
    .options(
        joinedload(Lesson.series),        # Load series relationship
        joinedload(Lesson.teacher),
        joinedload(Lesson.book)
    )
    .where(Lesson.id == lesson_id)
)
lesson = result.scalar_one_or_none()
```

2. **Object Reloading After Updates:**
```python
await update_lesson(lesson)
lesson = await get_lesson_by_id(lesson_id)  # Reload with fresh relationships
```

3. **Series Access:**
```python
# ❌ WRONG - these fields don't exist anymore
year = lesson.series_year
name = lesson.series_name

# ✅ CORRECT - use relationship
year = lesson.series.year
name = lesson.series.name
```

### Role-Based Access Control

Three roles (`bot/models/role.py`):
- **Admin** (role_id=1) - Full system access
- **Moderator** (role_id=2) - Manage lessons and teachers
- **User** (role_id=3) - Listen to lessons

**Decorators:**
- `@admin_required` - Admin-only handlers
- `@user_required_callback` - Registered users only

Admin configured via `ADMIN_TELEGRAM_ID` in `.env`.

### Audio File Management

**Storage Structure:**
```
bot/audio_files/
  └── <teacher_name>/
      └── <book_name>/
          └── <series_year>_<series_name>/
              └── урок_<number>_<title>.mp3
```

**Upload Process:**
1. Validate file (size, format)
2. Send to web-converter service (port 1992)
3. Convert to MP3 (64-128 kbps)
4. Store with sanitized filename
5. Extract duration via FFmpeg
6. Create Lesson record with file path

**Web Converter Service:**
- Separate Docker container on port 1992
- Handles audio format conversion (to MP3 64-128 kbps)
- Shared FFmpeg utilities between bot and converter (`bot/utils/`)
- Authentication via `WEB_CONVERTER_SECRET` in `.env`
- Service location: `web-converter/main.py`

**Key Utilities:**
- `bot/utils/ffmpeg_utils.py` - Audio processing (shared)
- `bot/utils/file_utils.py` - File operations
- `bot/utils/audio_converter.py` - Integration with web-converter service

### Timezone Handling

**Moscow Time (UTC+3):**
- All timestamps stored as naive datetime in Moscow time
- Database: `PGTZ=Europe/Moscow`
- Utility: `bot/utils/timezone_utils.py` → `get_moscow_now()`
- **Never use timezone-aware datetimes**

## Common Development Patterns

### Adding New Admin Entity

1. **Create model** in `bot/models/<entity>.py`
2. **Add CRUD** in `bot/services/database_service.py`
3. **Create handler** in `bot/handlers/admin/<entity>.py`:
   - List view with status (✅/❌)
   - Edit menu showing all fields
   - Single-window edit handlers (save message_id/chat_id)
   - Toggle active/inactive
   - Delete with confirmation
   - Single-window creation flow
4. **Register router** in `bot/handlers/admin/__init__.py`
5. **Add navigation** to admin panel

### Context-Aware Navigation Pattern

**Preserving user context in navigation:**

When users navigate from different entry points (themes → books → lessons vs teachers → series → lessons), handlers must preserve context for proper back navigation:

```python
# Pattern: Save context in FSM state
await state.update_data(
    lesson_id=lesson_id,
    teacher_id=teacher_id,  # May be None for general navigation
    bookmark_message_id=callback.message.message_id,
    bookmark_chat_id=callback.message.chat.id
)

# Pattern: Context-aware callbacks
data = await state.get_data()
teacher_id = data.get("teacher_id")

if teacher_id:
    # User came from teacher view - return there
    callback_data = f"teacher_{teacher_id}_play_lesson_{lesson_id}"
else:
    # User came from general view
    callback_data = f"lesson_{lesson_id}"
```

**Used extensively in:**
- `bot/handlers/user/bookmarks.py` - Bookmark management with context preservation
- `bot/handlers/user/lessons.py` - Lesson playback from different entry points
- `bot/handlers/user/teachers.py` - Teacher-specific lesson browsing

### Series-Related Queries

**Sorting by series:**
```python
# ❌ OLD (broken)
.order_by(Lesson.series_year.desc(), Lesson.series_name)

# ✅ NEW (correct)
.order_by(Lesson.series_id, Lesson.lesson_number)
```

**Grouping by series:**
```python
# Load lessons with series relationship
result = await session.execute(
    select(Lesson)
    .options(joinedload(Lesson.series))
    .where(Lesson.teacher_id == teacher_id)
    .order_by(Lesson.series_id)
)
lessons = result.scalars().unique().all()

# Group by series
series_map = {}
for lesson in lessons:
    if lesson.series_id:
        key = f"series_{lesson.series_id}"
        if key not in series_map:
            series_map[key] = {
                "series_id": lesson.series_id,
                "year": lesson.series.year,      # From relationship
                "name": lesson.series.name,      # From relationship
                "lessons": []
            }
        series_map[key]["lessons"].append(lesson)
```

### Feedback System Workflow

**Three-status model (`bot/models/feedback.py`):**

1. **new** (🆕) - User submits feedback
2. **replied** (✅) - Admin sends reply to user via bot
3. **closed** (🔒) - Feedback marked as resolved

**Admin workflow (`bot/handlers/admin/feedbacks.py`):**
```python
# View all feedbacks grouped by status
# Reply to user directly through bot (sends message to user's Telegram)
# Status automatically changes: new → replied → closed
# Timestamps tracked: created_at, replied_at, closed_at
```

**User workflow (`bot/handlers/user/feedback.py`):**
```python
# Simple form submission
# Receives admin reply as bot message
# Can view feedback history
```

### Database Migrations

When modifying models:
```bash
# Create migration
docker-compose exec bot alembic revision --autogenerate -m "Add field to Lesson"

# Review in alembic/versions/ (autogenerate isn't perfect)

# Apply
docker-compose exec bot alembic upgrade head
```

**Migration Notes:**
- Always review autogenerated code
- Test on copy of production data
- Include `upgrade()` and `downgrade()`
- For data migrations, write custom SQL

## Debugging

### Common Issues

**"Update is not handled" (short duration 13-16ms):**
- Filtered by aiogram before reaching handlers
- Caused by stale inline keyboards
- **Fix:** User closes/reopens Telegram app, or navigates fresh to menu

**DetachedInstanceError:**
- Accessing relationships outside session
- **Fix:** Use `joinedload()` when querying

**Handler not triggering:**
- Check handler order (specific before generic)
- Check filter syntax: `F.data.regexp(r"^pattern$")`
- Add debug logging

**Series data missing:**
- Ensure `joinedload(Lesson.series)` in query
- Reload object after updates: `lesson = await get_lesson_by_id(lesson_id)`

### Viewing Logs
```bash
# Real-time
docker-compose logs bot --follow

# Last N lines
docker-compose logs bot --tail=50

# Search
docker-compose logs bot | grep ERROR
```

## Testing Workflow

1. Make changes in `bot/` directory
2. Restart: `docker-compose restart bot`
3. Monitor: `docker-compose logs bot --follow`
4. Test via Telegram
5. Check DB via Adminer: http://localhost:8080

**Admin Setup:**
1. Send `/start` to bot
2. Get telegram_id from `/id`
3. Set in `.env`: `ADMIN_TELEGRAM_ID=<your_id>`
4. Restart: `docker-compose restart bot`

## Code Style

**Language:**
- Russian for UI text, comments (business logic), commit messages
- English for code (variables, functions, classes)

**Formatting:**
- HTML markup: `<b>Bold</b>`, emojis for clarity
- Callback data: `<action>_<entity>_<id>` format
- Regex handlers: `F.data.regexp(r"^edit_lesson_\d+$")`

**State Naming:**
- Descriptive: `LessonStates.edit_title` not `title_edit`

**Emoji Usage (STRICT):**
See `EMOJI_GUIDE.md` for full documentation. Key rules:

**Entities:**
- 📚 Темы (entity itself, not individual themes)
- 📖 Книги
- ✍️ Авторы книг
- 👤 Преподаватели
- 🎧 Уроки
- 📁 Серии (NOT 📚 or 🎙️ - this is critical!)
- 🎓 Тесты (NOT 📝 - 📝 is not used for tests!)
- ❓ Вопросы теста (ONLY for test questions, NOT for help/info)
- 👥 Пользователи
- 🏷️ Теги
- 📌 Закладки
- 💬 Обратная связь

**Actions:**
- ✏️ Edit short fields (name, title, year)
- 📄 Edit long fields (description, biography) - NOT 📝
- ➕ Add/Create
- 🗑️ Delete
- 🔙 Back
- ✅/❌ Yes/No, Active/Inactive
- ℹ️ Help/Info (NOT ❓ - ❓ is ONLY for test questions!)

## Critical Reminders

1. **Series fields removed** - Use `lesson.series_id` FK and `lesson.series` relationship only
2. **Single-window UX** - Save/restore message_id/chat_id, delete user inputs
3. **Eager load relationships** - `joinedload()` to avoid DetachedInstanceError
4. **Reload after updates** - Get fresh data: `obj = await get_<entity>_by_id(obj_id)`
5. **Handler order matters** - Specific patterns before generic
6. **Database service layer** - All DB ops through `database_service.py`
7. **Never commit `.env`** - Contains sensitive tokens
8. **Always use `await`** - Async ORM
9. **Try/except on message.delete()** - May already be deleted
10. **Moscow timezone** - Naive datetimes only
11. **Context preservation** - Save teacher_id/context for proper back navigation
12. **Emoji consistency** - 📁 for series, 🎓 for tests, ❓ ONLY for test questions, ℹ️ for help
13. **Bookmarks limit** - Max 20 per user, enforce in add_bookmark handler
14. **Feedback status flow** - new → replied → closed (update timestamps accordingly)
15. **Telegram file_id caching** - Store in `lesson.telegram_file_id` for faster re-sending
