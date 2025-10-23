"""
Сервис для работы с базой данных
"""
from typing import Optional, List
from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.models import (
    User, Role, Theme, BookAuthor, LessonTeacher,
    Book, Lesson, LessonSeries, async_session_maker,
    Test, TestQuestion, TestAttempt, Bookmark, Feedback
)
from bot.utils.timezone_utils import get_moscow_now


class DatabaseService:
    """Базовый класс для работы с базой данных"""
    
    @staticmethod
    async def get_session() -> AsyncSession:
        """Получение сессии базы данных"""
        return async_session_maker()


class UserService(DatabaseService):
    """Сервис для работы с пользователями"""
    
    @staticmethod
    async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
        """Получение пользователя по Telegram ID с загруженной ролью"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).options(joinedload(User.role)).where(User.telegram_id == telegram_id)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(user_id: int) -> Optional[User]:
        """Получение пользователя по внутреннему DB ID с загруженной ролью"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).options(joinedload(User.role)).where(User.id == user_id)
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    async def create_user(
        telegram_id: int, 
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role_id: int = 3  # Роль пользователя по умолчанию
    ) -> User:
        """Создание нового пользователя"""
        async with async_session_maker() as session:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                role_id=role_id
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
    
    @staticmethod
    async def get_or_create_user(
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> User:
        """Получение или создание пользователя"""
        user = await UserService.get_user_by_telegram_id(telegram_id)
        if not user:
            user = await UserService.create_user(
                telegram_id, username, first_name, last_name
            )
        return user
    
    @staticmethod
    async def update_user_role(telegram_id: int, role_id: int) -> bool:
        """Обновление роли пользователя по Telegram ID"""
        async with async_session_maker() as session:
            result = await session.execute(
                update(User).where(User.telegram_id == telegram_id).values(role_id=role_id)
            )
            await session.commit()
            return result.rowcount > 0

    @staticmethod
    async def update_user_role_by_id(user_id: int, role_id: int) -> bool:
        """Обновление роли пользователя по внутреннему DB ID"""
        async with async_session_maker() as session:
            result = await session.execute(
                update(User).where(User.id == user_id).values(role_id=role_id)
            )
            await session.commit()
            return result.rowcount > 0
    
    @staticmethod
    async def get_all_users(limit: int = 100, offset: int = 0) -> List[User]:
        """Получение списка всех пользователей с загруженными ролями"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).options(joinedload(User.role)).limit(limit).offset(offset)
            )
            return result.scalars().all()


class RoleService(DatabaseService):
    """Сервис для работы с ролями"""
    
    @staticmethod
    async def get_role_by_id(role_id: int) -> Optional[Role]:
        """Получение роли по ID"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Role).where(Role.id == role_id)
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    async def get_role_by_name(role_name: str) -> Optional[Role]:
        """Получение роли по названию"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Role).where(Role.name == role_name)
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    async def get_all_roles() -> List[Role]:
        """Получение всех ролей"""
        async with async_session_maker() as session:
            result = await session.execute(select(Role))
            return result.scalars().all()


class ThemeService(DatabaseService):
    """Сервис для работы с темами"""
    
    @staticmethod
    async def get_all_active_themes() -> List[Theme]:
        """Получение всех активных тем"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Theme).where(Theme.is_active == True).order_by(Theme.sort_order)
            )
            return result.scalars().all()
    
    @staticmethod
    async def get_theme_by_id(theme_id: int) -> Optional[Theme]:
        """Получение темы по ID (с загруженными книгами)"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Theme)
                .options(joinedload(Theme.books).joinedload(Book.lessons))
                .where(Theme.id == theme_id)
            )
            return result.unique().scalar_one_or_none()
    
    @staticmethod
    async def get_theme_by_name(name: str) -> Optional[Theme]:
        """Получение темы по названию"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Theme).where(Theme.name == name)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def create_theme(name: str, desc: str = None, sort_order: int = 0) -> Theme:
        """Создание новой темы"""
        async with async_session_maker() as session:
            theme = Theme(
                name=name,
                desc=desc,
                sort_order=sort_order
            )
            session.add(theme)
            await session.commit()
            await session.refresh(theme)
            return theme


class BookAuthorService(DatabaseService):
    """Сервис для работы с авторами книг"""
    
    @staticmethod
    async def get_all_active_authors() -> List[BookAuthor]:
        """Получение всех активных авторов"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(BookAuthor).where(BookAuthor.is_active == True).order_by(BookAuthor.name)
            )
            return result.scalars().all()
    
    @staticmethod
    async def get_author_by_id(author_id: int) -> Optional[BookAuthor]:
        """Получение автора по ID"""
        async with async_session_maker() as session:
            session.expire_on_commit = False
            result = await session.execute(
                select(BookAuthor)
                .options(joinedload(BookAuthor.books))
                .where(BookAuthor.id == author_id)
            )
            return result.unique().scalar_one_or_none()

    @staticmethod
    async def get_author_by_name(name: str) -> Optional[BookAuthor]:
        """Получение автора по имени"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(BookAuthor).where(BookAuthor.name == name)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def create_author(
        name: str,
        biography: str = None,
        birth_year: int = None,
        death_year: int = None
    ) -> BookAuthor:
        """Создание нового автора"""
        async with async_session_maker() as session:
            author = BookAuthor(
                name=name,
                biography=biography,
                birth_year=birth_year,
                death_year=death_year
            )
            session.add(author)
            await session.commit()
            await session.refresh(author)
            return author


class LessonTeacherService(DatabaseService):
    """Сервис для работы с преподавателями уроков"""
    
    @staticmethod
    async def get_all_active_teachers() -> List[LessonTeacher]:
        """Получение всех активных преподавателей"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(LessonTeacher).where(LessonTeacher.is_active == True).order_by(LessonTeacher.name)
            )
            return result.scalars().all()
    
    @staticmethod
    async def get_teacher_by_id(teacher_id: int) -> Optional[LessonTeacher]:
        """Получение преподавателя по ID"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(LessonTeacher).where(LessonTeacher.id == teacher_id)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def get_teacher_by_name(name: str) -> Optional[LessonTeacher]:
        """Получение преподавателя по имени"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(LessonTeacher).where(LessonTeacher.name == name)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def create_teacher(name: str, biography: str = None) -> LessonTeacher:
        """Создание нового преподавателя"""
        async with async_session_maker() as session:
            teacher = LessonTeacher(
                name=name,
                biography=biography
            )
            session.add(teacher)
            await session.commit()
            await session.refresh(teacher)
            return teacher


class BookService(DatabaseService):
    """Сервис для работы с книгами"""
    
    @staticmethod
    async def get_books_by_theme(theme_id: Optional[int]) -> List[Book]:
        """Получение книг по теме (включая книги без темы если theme_id=None)"""
        async with async_session_maker() as session:
            # Формируем условие для theme_id
            if theme_id is None:
                theme_condition = Book.theme_id.is_(None)
            else:
                theme_condition = Book.theme_id == theme_id

            result = await session.execute(
                select(Book)
                .options(joinedload(Book.author))
                .outerjoin(Book.author)  # LEFT JOIN - включает книги без автора
                .where(
                    theme_condition,
                    Book.is_active == True,
                    (BookAuthor.is_active == True) | (BookAuthor.id == None)  # Активный автор ИЛИ без автора
                )
                .order_by(Book.sort_order)
            )
            return result.scalars().all()
    
    @staticmethod
    async def get_books_without_theme_count() -> int:
        """Получение количества активных книг без темы"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(func.count(Book.id))
                .outerjoin(Book.author)
                .where(
                    Book.theme_id.is_(None),
                    Book.is_active == True,
                    (BookAuthor.is_active == True) | (BookAuthor.id == None)
                )
            )
            return result.scalar() or 0

    @staticmethod
    async def get_book_by_id(book_id: int) -> Optional[Book]:
        """Получение книги по ID (с загруженными связанными данными)"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Book)
                .options(
                    joinedload(Book.author),
                    joinedload(Book.theme),
                    joinedload(Book.lessons)
                )
                .where(Book.id == book_id)
            )
            return result.unique().scalar_one_or_none()
    
    @staticmethod
    async def create_book(
        theme_id: int,
        author_id: int,
        name: str,
        desc: str = None,
        sort_order: int = 0
    ) -> Book:
        """Создание новой книги"""
        async with async_session_maker() as session:
            book = Book(
                theme_id=theme_id,
                author_id=author_id,
                name=name,
                desc=desc,
                sort_order=sort_order
            )
            session.add(book)
            await session.commit()
            await session.refresh(book)
            return book


class LessonService(DatabaseService):
    """Сервис для работы с уроками"""
    
    @staticmethod
    async def get_lessons_by_book(book_id: int) -> List[Lesson]:
        """Получение уроков по книге"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Lesson)
                .options(joinedload(Lesson.teacher), joinedload(Lesson.book))
                .where(Lesson.book_id == book_id, Lesson.is_active == True)
                .order_by(Lesson.lesson_number)
            )
            return result.scalars().all()

    @staticmethod
    async def get_lessons_by_series(series_id: int) -> List[Lesson]:
        """Получение активных уроков по серии"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Lesson)
                .options(
                    joinedload(Lesson.teacher),
                    joinedload(Lesson.book).joinedload(Book.author),
                    joinedload(Lesson.series)
                )
                .where(Lesson.series_id == series_id, Lesson.is_active == True)
                .order_by(Lesson.lesson_number)
            )
            return result.scalars().all()

    @staticmethod
    async def get_lesson_by_id(lesson_id: int) -> Optional[Lesson]:
        """Получение урока по ID"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Lesson)
                .options(
                    joinedload(Lesson.teacher),
                    joinedload(Lesson.book).joinedload(Book.author),
                    joinedload(Lesson.book).joinedload(Book.theme),
                    joinedload(Lesson.theme)
                )
                .where(Lesson.id == lesson_id)
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    async def create_lesson(
        book_id: int,
        teacher_id: int,
        title: str,
        series_year: int,
        series_name: str,
        description: str = None,
        audio_path: str = None,
        lesson_number: int = None,
        duration_seconds: int = None,
        tags: str = None
    ) -> Lesson:
        """Создание нового урока"""
        async with async_session_maker() as session:
            lesson = Lesson(
                book_id=book_id,
                teacher_id=teacher_id,
                title=title,
                description=description,
                series_year=series_year,
                series_name=series_name,
                audio_path=audio_path,
                lesson_number=lesson_number,
                duration_seconds=duration_seconds,
                tags=tags
            )
            session.add(lesson)
            await session.commit()
            await session.refresh(lesson)
            return lesson
    
    @staticmethod
    async def search_lessons(query: str) -> List[Lesson]:
        """Поиск уроков по запросу (только из активных книг с активными авторами или без автора)"""
        async with async_session_maker() as session:
            search_pattern = f"%{query}%"
            result = await session.execute(
                select(Lesson)
                .join(Lesson.book)
                .outerjoin(Book.author)  # LEFT JOIN - включает книги без автора
                .where(
                    Lesson.is_active == True,
                    Book.is_active == True,  # Проверка активности книги
                    (BookAuthor.is_active == True) | (BookAuthor.id == None),  # Активный автор ИЛИ без автора
                    (func.lower(Lesson.title).like(search_pattern) |
                     func.lower(Lesson.description).like(search_pattern) |
                     func.lower(Lesson.tags).like(search_pattern))
                )
            )
            return result.scalars().all()


# Удобные функции для использования в обработчиках
async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    """Получение пользователя по Telegram ID"""
    return await UserService.get_user_by_telegram_id(telegram_id)


async def get_user_with_role(telegram_id: int) -> Optional[User]:
    """Получение пользователя с загруженной ролью для проверки прав"""
    async with async_session_maker() as session:
        from sqlalchemy.orm import selectinload
        result = await session.execute(
            select(User).options(selectinload(User.role)).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        # Добавляем логирование для отладки
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Get user with role - User ID: {telegram_id}, User: {user}, Role: {user.role if user else None}, Role name: {user.role.name if user and user.role else None}")
        
        return user


async def get_all_themes() -> List[Theme]:
    """Получение всех тем (включая неактивные)"""
    async with async_session_maker() as session:
        result = await session.execute(select(Theme).order_by(Theme.sort_order))
        return result.scalars().all()


async def get_theme_by_id(theme_id: int) -> Optional[Theme]:
    """Получение темы по ID"""
    return await ThemeService.get_theme_by_id(theme_id)


async def get_theme_by_name(name: str) -> Optional[Theme]:
    """Получение темы по названию"""
    return await ThemeService.get_theme_by_name(name)


async def create_theme(name: str, desc: str = None, is_active: bool = True, sort_order: int = 0) -> Theme:
    """Создание новой темы"""
    async with async_session_maker() as session:
        theme = Theme(
            name=name,
            desc=desc,
            is_active=is_active,
            sort_order=sort_order
        )
        session.add(theme)
        await session.commit()
        await session.refresh(theme)
        return theme


async def update_theme(theme: Theme) -> Theme:
    """Обновление темы"""
    async with async_session_maker() as session:
        await session.merge(theme)
        await session.commit()
        return theme


async def delete_theme(theme_id: int) -> bool:
    """Удаление темы"""
    async with async_session_maker() as session:
        result = await session.execute(
            delete(Theme).where(Theme.id == theme_id)
        )
        await session.commit()
        return result.rowcount > 0


async def get_all_book_authors() -> List[BookAuthor]:
    """Получение всех авторов книг (включая неактивных)"""
    async with async_session_maker() as session:
        result = await session.execute(select(BookAuthor).order_by(BookAuthor.name))
        return result.scalars().all()


async def get_book_author_by_id(author_id: int) -> Optional[BookAuthor]:
    """Получение автора книги по ID"""
    return await BookAuthorService.get_author_by_id(author_id)


async def get_book_author_by_name(name: str) -> Optional[BookAuthor]:
    """Получение автора книги по имени"""
    return await BookAuthorService.get_author_by_name(name)


async def create_book_author(name: str, biography: str = None, is_active: bool = True) -> BookAuthor:
    """Создание нового автора книги"""
    async with async_session_maker() as session:
        author = BookAuthor(
            name=name,
            biography=biography,
            is_active=is_active
        )
        session.add(author)
        await session.commit()
        await session.refresh(author)
        return author


async def update_book_author(author: BookAuthor) -> BookAuthor:
    """Обновление автора книги"""
    async with async_session_maker() as session:
        await session.merge(author)
        await session.commit()
        return author


async def delete_book_author(author_id: int) -> bool:
    """Удаление автора книги"""
    async with async_session_maker() as session:
        result = await session.execute(
            delete(BookAuthor).where(BookAuthor.id == author_id)
        )
        await session.commit()
        return result.rowcount > 0


async def get_all_lesson_teachers() -> List[LessonTeacher]:
    """Получение всех преподавателей (включая неактивных)"""
    async with async_session_maker() as session:
        result = await session.execute(select(LessonTeacher).order_by(LessonTeacher.name))
        return result.scalars().all()


async def get_lesson_teacher_by_id(teacher_id: int) -> Optional[LessonTeacher]:
    """Получение преподавателя по ID"""
    return await LessonTeacherService.get_teacher_by_id(teacher_id)


async def get_lesson_teacher_by_name(name: str) -> Optional[LessonTeacher]:
    """Получение преподавателя по имени"""
    return await LessonTeacherService.get_teacher_by_name(name)


async def create_lesson_teacher(name: str, biography: str = None, is_active: bool = True) -> LessonTeacher:
    """Создание нового преподавателя"""
    async with async_session_maker() as session:
        teacher = LessonTeacher(
            name=name,
            biography=biography,
            is_active=is_active
        )
        session.add(teacher)
        await session.commit()
        await session.refresh(teacher)
        return teacher


async def update_lesson_teacher(teacher: LessonTeacher) -> LessonTeacher:
    """Обновление преподавателя"""
    async with async_session_maker() as session:
        await session.merge(teacher)
        await session.commit()
        return teacher


async def delete_lesson_teacher(teacher_id: int) -> bool:
    """Удаление преподавателя"""
    async with async_session_maker() as session:
        result = await session.execute(
            delete(LessonTeacher).where(LessonTeacher.id == teacher_id)
        )
        await session.commit()
        return result.rowcount > 0


async def get_all_books() -> List[Book]:
    """Получение всех книг (включая неактивные)"""
    async with async_session_maker() as session:
        result = await session.execute(select(Book).order_by(Book.sort_order))
        return result.scalars().all()


async def get_book_by_id(book_id: int) -> Optional[Book]:
    """Получение книги по ID"""
    return await BookService.get_book_by_id(book_id)


async def create_book(
    name: str,
    desc: str = None,
    theme_id: int = None,
    author_id: int = None,
    is_active: bool = True,
    sort_order: int = 0
) -> Book:
    """Создание новой книги"""
    async with async_session_maker() as session:
        book = Book(
            name=name,
            desc=desc,
            theme_id=theme_id,
            author_id=author_id,
            is_active=is_active,
            sort_order=sort_order
        )
        session.add(book)
        await session.commit()
        await session.refresh(book)
        return book


async def update_book(book: Book) -> Book:
    """Обновление книги"""
    async with async_session_maker() as session:
        await session.merge(book)
        await session.commit()
        return book


async def delete_book(book_id: int) -> bool:
    """Удаление книги"""
    async with async_session_maker() as session:
        result = await session.execute(
            delete(Book).where(Book.id == book_id)
        )
        await session.commit()
        return result.rowcount > 0


async def get_all_lessons() -> List[Lesson]:
    """Получение всех уроков (включая неактивные)"""
    async with async_session_maker() as session:
        result = await session.execute(select(Lesson).order_by(Lesson.lesson_number))
        return result.scalars().all()


async def get_lesson_by_id(lesson_id: int) -> Optional[Lesson]:
    """Получение урока по ID"""
    return await LessonService.get_lesson_by_id(lesson_id)


async def create_lesson(
    title: str,
    series_id: int,  # Обязательное поле - связь с серией
    description: str = None,
    audio_file_path: str = None,
    duration_seconds: int = None,
    lesson_number: int = None,
    book_id: int = None,
    theme_id: int = None,
    teacher_id: int = None,
    tags: str = None,
    is_active: bool = True
) -> Lesson:
    """Создание нового урока"""
    async with async_session_maker() as session:
        lesson = Lesson(
            title=title,
            description=description,
            series_id=series_id,
            audio_path=audio_file_path,
            duration_seconds=duration_seconds,
            lesson_number=lesson_number,
            book_id=book_id,
            theme_id=theme_id,
            teacher_id=teacher_id,
            tags=tags,
            is_active=is_active
        )
        session.add(lesson)
        await session.commit()
        await session.refresh(lesson)
        return lesson


async def update_lesson(lesson: Lesson) -> Lesson:
    """Обновление урока"""
    async with async_session_maker() as session:
        await session.merge(lesson)
        await session.commit()
        return lesson


async def delete_lesson(lesson_id: int) -> bool:
    """Удаление урока"""
    async with async_session_maker() as session:
        result = await session.execute(
            delete(Lesson).where(Lesson.id == lesson_id)
        )
        await session.commit()
        return result.rowcount > 0


# ===============================
# Lesson Series Operations
# ===============================

async def get_all_lesson_series() -> List[LessonSeries]:
    """Получение всех серий уроков"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(LessonSeries)
            .options(
                joinedload(LessonSeries.teacher),
                joinedload(LessonSeries.book),
                joinedload(LessonSeries.theme)
            )
            .order_by(LessonSeries.year.desc(), LessonSeries.name)
        )
        return result.scalars().unique().all()


async def get_series_by_teacher(teacher_id: int) -> List[LessonSeries]:
    """Получение всех серий преподавателя"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(LessonSeries)
            .options(
                joinedload(LessonSeries.teacher),
                joinedload(LessonSeries.book),
                joinedload(LessonSeries.theme),
                joinedload(LessonSeries.lessons)
            )
            .where(LessonSeries.teacher_id == teacher_id)
            .order_by(LessonSeries.year.desc(), LessonSeries.name)
        )
        return result.scalars().unique().all()


async def get_themes_by_teacher(teacher_id: int) -> List[Theme]:
    """Получение уникальных тем преподавателя"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Theme)
            .join(LessonSeries, LessonSeries.theme_id == Theme.id)
            .where(
                LessonSeries.teacher_id == teacher_id,
                LessonSeries.is_active == True,
                Theme.is_active == True
            )
            .distinct()
            .order_by(Theme.name)
        )
        return result.scalars().unique().all()


async def get_books_by_teacher_and_theme(teacher_id: int, theme_id: int) -> List[Book]:
    """Получение книг преподавателя по теме"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Book)
            .options(
                joinedload(Book.author),
                joinedload(Book.theme)
            )
            .join(LessonSeries, LessonSeries.book_id == Book.id)
            .where(
                LessonSeries.teacher_id == teacher_id,
                Book.theme_id == theme_id,
                LessonSeries.is_active == True,
                Book.is_active == True
            )
            .distinct()
            .order_by(Book.name)
        )
        return result.scalars().unique().all()


async def get_series_by_teacher_and_book(teacher_id: int, book_id: int) -> List[LessonSeries]:
    """Получение серий преподавателя по книге"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(LessonSeries)
            .options(
                joinedload(LessonSeries.teacher),
                joinedload(LessonSeries.book),
                joinedload(LessonSeries.theme),
                joinedload(LessonSeries.lessons)
            )
            .where(
                LessonSeries.teacher_id == teacher_id,
                LessonSeries.book_id == book_id,
                LessonSeries.is_active == True
            )
            .order_by(LessonSeries.year.desc(), LessonSeries.name)
        )
        return result.scalars().unique().all()


async def get_series_by_book(book_id: int) -> List[LessonSeries]:
    """Получение всех активных серий книги"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(LessonSeries)
            .options(
                joinedload(LessonSeries.teacher),
                joinedload(LessonSeries.book),
                joinedload(LessonSeries.theme),
                joinedload(LessonSeries.lessons)
            )
            .where(LessonSeries.book_id == book_id)
            .where(LessonSeries.is_active == True)
            .order_by(LessonSeries.year.desc(), LessonSeries.name)
        )
        return result.scalars().unique().all()


async def get_series_by_id(series_id: int) -> Optional[LessonSeries]:
    """Получение серии по ID"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(LessonSeries)
            .options(
                joinedload(LessonSeries.teacher),
                joinedload(LessonSeries.book).joinedload(Book.author),
                joinedload(LessonSeries.book).joinedload(Book.theme),
                joinedload(LessonSeries.theme),
                joinedload(LessonSeries.lessons)
            )
            .where(LessonSeries.id == series_id)
        )
        return result.unique().scalar_one_or_none()


async def check_lesson_number_exists(series_id: int, lesson_number: int, exclude_lesson_id: Optional[int] = None) -> bool:
    """
    Проверка существования урока с таким номером в серии

    Args:
        series_id: ID серии
        lesson_number: Номер урока для проверки
        exclude_lesson_id: ID урока, который нужно исключить из проверки (для редактирования)

    Returns:
        True если урок с таким номером уже существует в серии, False если нет
    """
    async with async_session_maker() as session:
        query = select(Lesson).where(
            and_(
                Lesson.series_id == series_id,
                Lesson.lesson_number == lesson_number
            )
        )

        # Если редактируем урок, исключаем его из проверки
        if exclude_lesson_id:
            query = query.where(Lesson.id != exclude_lesson_id)

        result = await session.execute(query)
        existing_lesson = result.scalar_one_or_none()

        return existing_lesson is not None


async def create_lesson_series(
    name: str,
    year: int,
    teacher_id: int,
    description: Optional[str] = None,
    book_id: Optional[int] = None,
    theme_id: Optional[int] = None,
    is_completed: bool = False,
    order: int = 0,
    is_active: bool = True
) -> LessonSeries:
    """Создание новой серии уроков"""
    async with async_session_maker() as session:
        series = LessonSeries(
            name=name,
            year=year,
            teacher_id=teacher_id,
            description=description,
            book_id=book_id,
            theme_id=theme_id,
            is_completed=is_completed,
            order=order,
            is_active=is_active
        )
        session.add(series)
        await session.commit()
        await session.refresh(series)
        return series


async def update_lesson_series(series: LessonSeries) -> LessonSeries:
    """Обновление серии уроков"""
    async with async_session_maker() as session:
        await session.merge(series)
        await session.commit()
        return series


async def delete_lesson_series(series_id: int) -> bool:
    """Удаление серии уроков"""
    async with async_session_maker() as session:
        result = await session.execute(
            delete(LessonSeries).where(LessonSeries.id == series_id)
        )
        await session.commit()
        return result.rowcount > 0


async def regenerate_teacher_lessons_titles(teacher_id: int) -> int:
    """
    Регенерирует названия (title) всех уроков преподавателя после изменения teacher.name
    Также сбрасывает telegram_file_id чтобы в плеере обновилось название
    Возвращает количество обновлённых уроков
    """
    async with async_session_maker() as session:
        # Загружаем преподавателя
        result = await session.execute(
            select(LessonTeacher).where(LessonTeacher.id == teacher_id)
        )
        teacher = result.scalar_one_or_none()

        if not teacher:
            return 0

        # Загружаем все уроки этого преподавателя
        result = await session.execute(
            select(Lesson)
            .where(Lesson.teacher_id == teacher_id)
            .options(
                joinedload(Lesson.series),
                joinedload(Lesson.book)
            )
        )
        lessons = result.scalars().unique().all()

        updated_count = 0

        # Функция генерации названия
        def generate_lesson_title(teacher_name: str, book_name: str, series_year: int, series_name: str, lesson_number: int) -> str:
            parts = []
            if teacher_name:
                parts.append(teacher_name.replace(" ", "_"))
            if book_name:
                parts.append(book_name.replace(" ", "_"))
            parts.append(str(series_year))
            parts.append(series_name.replace(" ", "_"))
            parts.append(f"урок_{lesson_number}")
            return "_".join(parts)

        # Обновляем каждый урок
        for lesson in lessons:
            if not lesson.series:
                continue

            new_title = generate_lesson_title(
                teacher_name=teacher.name,
                book_name=lesson.book.name if lesson.book else "",
                series_year=lesson.series.year,
                series_name=lesson.series.name,
                lesson_number=lesson.lesson_number if lesson.lesson_number else 0
            )

            # Обновляем только если название изменилось
            if lesson.title != new_title:
                lesson.title = new_title
                lesson.telegram_file_id = None  # Сбрасываем кэш
                updated_count += 1

        await session.commit()
        return updated_count


async def regenerate_book_lessons_titles(book_id: int) -> int:
    """
    Регенерирует названия (title) всех уроков книги после изменения book.name
    Также сбрасывает telegram_file_id чтобы в плеере обновилось название
    Возвращает количество обновлённых уроков
    """
    async with async_session_maker() as session:
        # Загружаем книгу
        result = await session.execute(
            select(Book).where(Book.id == book_id)
        )
        book = result.scalar_one_or_none()

        if not book:
            return 0

        # Загружаем все уроки этой книги
        result = await session.execute(
            select(Lesson)
            .where(Lesson.book_id == book_id)
            .options(
                joinedload(Lesson.series),
                joinedload(Lesson.teacher)
            )
        )
        lessons = result.scalars().unique().all()

        updated_count = 0

        # Функция генерации названия
        def generate_lesson_title(teacher_name: str, book_name: str, series_year: int, series_name: str, lesson_number: int) -> str:
            parts = []
            if teacher_name:
                parts.append(teacher_name.replace(" ", "_"))
            if book_name:
                parts.append(book_name.replace(" ", "_"))
            parts.append(str(series_year))
            parts.append(series_name.replace(" ", "_"))
            parts.append(f"урок_{lesson_number}")
            return "_".join(parts)

        # Обновляем каждый урок
        for lesson in lessons:
            if not lesson.series:
                continue

            new_title = generate_lesson_title(
                teacher_name=lesson.teacher.name if lesson.teacher else "",
                book_name=book.name,
                series_year=lesson.series.year,
                series_name=lesson.series.name,
                lesson_number=lesson.lesson_number if lesson.lesson_number else 0
            )

            # Обновляем только если название изменилось
            if lesson.title != new_title:
                lesson.title = new_title
                lesson.telegram_file_id = None  # Сбрасываем кэш
                updated_count += 1

        await session.commit()
        return updated_count


async def regenerate_lesson_title(lesson_id: int) -> bool:
    """
    Регенерирует название (title) конкретного урока после изменения lesson.lesson_number
    Также сбрасывает telegram_file_id чтобы в плеере обновилось название
    Возвращает True если название было обновлено
    """
    async with async_session_maker() as session:
        # Загружаем урок со всеми relationships
        result = await session.execute(
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(
                joinedload(Lesson.series),
                joinedload(Lesson.teacher),
                joinedload(Lesson.book)
            )
        )
        lesson = result.scalar_one_or_none()

        if not lesson or not lesson.series:
            return False

        # Функция генерации названия
        def generate_lesson_title(teacher_name: str, book_name: str, series_year: int, series_name: str, lesson_number: int) -> str:
            parts = []
            if teacher_name:
                parts.append(teacher_name.replace(" ", "_"))
            if book_name:
                parts.append(book_name.replace(" ", "_"))
            parts.append(str(series_year))
            parts.append(series_name.replace(" ", "_"))
            parts.append(f"урок_{lesson_number}")
            return "_".join(parts)

        new_title = generate_lesson_title(
            teacher_name=lesson.teacher.name if lesson.teacher else "",
            book_name=lesson.book.name if lesson.book else "",
            series_year=lesson.series.year,
            series_name=lesson.series.name,
            lesson_number=lesson.lesson_number if lesson.lesson_number else 0
        )

        # Обновляем только если название изменилось
        if lesson.title != new_title:
            lesson.title = new_title
            lesson.telegram_file_id = None  # Сбрасываем кэш
            await session.commit()
            return True

        return False


async def regenerate_series_lessons_titles(series_id: int) -> int:
    """
    Регенерирует названия (title) всех уроков серии после изменения series.name или series.year
    Также сбрасывает telegram_file_id чтобы в плеере обновилось название
    Возвращает количество обновлённых уроков
    """
    async with async_session_maker() as session:
        # Загружаем серию с relationships
        result = await session.execute(
            select(LessonSeries)
            .where(LessonSeries.id == series_id)
            .options(
                joinedload(LessonSeries.teacher),
                joinedload(LessonSeries.book)
            )
        )
        series = result.scalar_one_or_none()

        if not series:
            return 0

        # Загружаем все уроки этой серии
        result = await session.execute(
            select(Lesson)
            .where(Lesson.series_id == series_id)
            .options(
                joinedload(Lesson.teacher),
                joinedload(Lesson.book)
            )
        )
        lessons = result.scalars().unique().all()

        updated_count = 0

        # Функция генерации названия
        def generate_lesson_title(teacher_name: str, book_name: str, series_year: int, series_name: str, lesson_number: int) -> str:
            parts = []
            if teacher_name:
                parts.append(teacher_name.replace(" ", "_"))
            if book_name:
                parts.append(book_name.replace(" ", "_"))
            parts.append(str(series_year))
            parts.append(series_name.replace(" ", "_"))
            parts.append(f"урок_{lesson_number}")
            return "_".join(parts)

        # Обновляем каждый урок
        for lesson in lessons:
            new_title = generate_lesson_title(
                teacher_name=lesson.teacher.name if lesson.teacher else "",
                book_name=lesson.book.name if lesson.book else "",
                series_year=series.year,
                series_name=series.name,
                lesson_number=lesson.lesson_number if lesson.lesson_number else 0
            )

            # Обновляем только если название изменилось
            if lesson.title != new_title:
                lesson.title = new_title
                lesson.telegram_file_id = None  # Сбрасываем кэш
                updated_count += 1

        await session.commit()
        return updated_count


async def bulk_update_series_lessons(series_id: int, book_id: Optional[int] = None, theme_id: Optional[int] = None) -> int:
    """
    Массовое обновление уроков серии
    Обновляет book_id и/или theme_id для всех уроков серии
    Возвращает количество обновлённых уроков
    """
    async with async_session_maker() as session:
        # Формируем values для обновления
        values = {}
        if book_id is not None:
            values['book_id'] = book_id
        if theme_id is not None:
            values['theme_id'] = theme_id

        if not values:
            return 0

        result = await session.execute(
            update(Lesson)
            .where(Lesson.series_id == series_id)
            .values(**values)
        )
        await session.commit()
        return result.rowcount


async def bulk_update_book_lessons(book_id: int, theme_id: Optional[int] = None) -> int:
    """
    Массовое обновление уроков книги во ВСЕХ сериях
    Обновляет theme_id для всех уроков этой книги
    Возвращает количество обновлённых уроков
    """
    async with async_session_maker() as session:
        if theme_id is None:
            return 0

        result = await session.execute(
            update(Lesson)
            .where(Lesson.book_id == book_id)
            .values(theme_id=theme_id)
        )
        await session.commit()
        return result.rowcount


# ==================== ТЕСТЫ ====================

async def get_all_tests() -> List[Test]:
    """Получить все тесты"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Test)
            .options(
                joinedload(Test.teacher),
                joinedload(Test.series),
                joinedload(Test.questions)
            )
            .order_by(Test.created_at.desc())
        )
        return list(result.scalars().unique().all())


async def get_test_by_id(test_id: int) -> Optional[Test]:
    """Получить тест по ID"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Test)
            .options(
                joinedload(Test.teacher),
                joinedload(Test.series),
                joinedload(Test.questions).joinedload(TestQuestion.lesson)
            )
            .where(Test.id == test_id)
        )
        return result.unique().scalar_one_or_none()


async def get_test_by_series(series_id: int) -> Optional[Test]:
    """Получить тест по серии (один тест на серию)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Test)
            .options(
                joinedload(Test.teacher),
                joinedload(Test.series),
                joinedload(Test.questions).joinedload(TestQuestion.lesson)
            )
            .where(Test.series_id == series_id)
        )
        return result.unique().scalar_one_or_none()


async def get_tests_by_teacher(teacher_id: int) -> List[Test]:
    """Получить все тесты преподавателя"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Test)
            .options(
                joinedload(Test.teacher),
                joinedload(Test.series),
                joinedload(Test.questions)
            )
            .where(Test.teacher_id == teacher_id)
            .order_by(Test.created_at.desc())
        )
        return list(result.scalars().unique().all())


async def create_test(
    title: str,
    series_id: int,
    teacher_id: int,
    description: Optional[str] = None,
    passing_score: int = 80,
    time_per_question_seconds: int = 30,
    order: int = 0
) -> Test:
    """Создать новый тест (один тест на серию)"""
    async with async_session_maker() as session:
        test = Test(
            title=title,
            series_id=series_id,
            teacher_id=teacher_id,
            description=description,
            passing_score=passing_score,
            time_per_question_seconds=time_per_question_seconds,
            order=order,
            questions_count=0
        )
        session.add(test)
        await session.commit()
        await session.refresh(test)
        return test


async def update_test(test: Test) -> Test:
    """Обновить тест"""
    async with async_session_maker() as session:
        await session.merge(test)
        await session.commit()
        return test


async def delete_test(test_id: int) -> bool:
    """Удалить тест"""
    async with async_session_maker() as session:
        result = await session.execute(
            delete(Test).where(Test.id == test_id)
        )
        await session.commit()
        return result.rowcount > 0


async def toggle_test_active(test_id: int) -> Optional[Test]:
    """Переключить активность теста"""
    test = await get_test_by_id(test_id)
    if test:
        test.is_active = not test.is_active
        return await update_test(test)
    return None


async def update_test_questions_count(test_id: int) -> Test:
    """Обновить счётчик вопросов в тесте"""
    async with async_session_maker() as session:
        # Считаем вопросы
        result = await session.execute(
            select(func.count(TestQuestion.id)).where(TestQuestion.test_id == test_id)
        )
        count = result.scalar() or 0

        # Обновляем тест
        await session.execute(
            update(Test)
            .where(Test.id == test_id)
            .values(questions_count=count)
        )
        await session.commit()

    return await get_test_by_id(test_id)


# ==================== ВОПРОСЫ ТЕСТОВ ====================

async def get_questions_by_test(test_id: int) -> List[TestQuestion]:
    """Получить все вопросы теста"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(TestQuestion)
            .options(joinedload(TestQuestion.lesson))
            .where(TestQuestion.test_id == test_id)
            .order_by(TestQuestion.lesson_id, TestQuestion.order)
        )
        return list(result.scalars().unique().all())


async def get_questions_by_lesson(test_id: int, lesson_id: int) -> List[TestQuestion]:
    """Получить вопросы теста для конкретного урока"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(TestQuestion)
            .options(joinedload(TestQuestion.lesson))
            .where(
                and_(
                    TestQuestion.test_id == test_id,
                    TestQuestion.lesson_id == lesson_id
                )
            )
            .order_by(TestQuestion.order)
        )
        return list(result.scalars().unique().all())


async def get_question_by_id(question_id: int) -> Optional[TestQuestion]:
    """Получить вопрос по ID"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(TestQuestion).where(TestQuestion.id == question_id)
        )
        return result.scalar_one_or_none()


async def create_question(
    test_id: int,
    lesson_id: int,
    question_text: str,
    options: list,
    correct_answer_index: int,
    explanation: Optional[str] = None,
    order: int = 0,
    points: int = 1
) -> TestQuestion:
    """Создать новый вопрос (с привязкой к уроку)"""
    async with async_session_maker() as session:
        question = TestQuestion(
            test_id=test_id,
            lesson_id=lesson_id,
            question_text=question_text,
            options=options,
            correct_answer_index=correct_answer_index,
            explanation=explanation,
            order=order,
            points=points
        )
        session.add(question)
        await session.commit()
        await session.refresh(question)

    # Обновляем счётчик вопросов в тесте
    await update_test_questions_count(test_id)

    return question


async def update_question(question: TestQuestion) -> TestQuestion:
    """Обновить вопрос"""
    async with async_session_maker() as session:
        await session.merge(question)
        await session.commit()
        return question


async def delete_question(question_id: int) -> bool:
    """Удалить вопрос"""
    # Сначала получаем test_id
    question = await get_question_by_id(question_id)
    if not question:
        return False

    test_id = question.test_id

    async with async_session_maker() as session:
        result = await session.execute(
            delete(TestQuestion).where(TestQuestion.id == question_id)
        )
        await session.commit()
        success = result.rowcount > 0

    if success:
        # Обновляем счётчик вопросов
        await update_test_questions_count(test_id)

    return success


async def reorder_questions(test_id: int, question_ids_in_order: List[int]) -> bool:
    """Изменить порядок вопросов"""
    async with async_session_maker() as session:
        for index, question_id in enumerate(question_ids_in_order):
            await session.execute(
                update(TestQuestion)
                .where(TestQuestion.id == question_id)
                .values(order=index)
            )
        await session.commit()
        return True


# ==================== ПОПЫТКИ ПРОХОЖДЕНИЯ ТЕСТОВ ====================

async def get_attempts_by_test(test_id: int) -> List[TestAttempt]:
    """Получить все попытки по тесту"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(TestAttempt)
            .options(
                joinedload(TestAttempt.user),
                joinedload(TestAttempt.test)
            )
            .where(TestAttempt.test_id == test_id)
            .order_by(TestAttempt.started_at.desc())
        )
        return list(result.scalars().unique().all())


async def get_attempts_by_user(user_id: int, test_id: Optional[int] = None) -> List[TestAttempt]:
    """Получить все попытки пользователя (опционально фильтруя по test_id)"""
    async with async_session_maker() as session:
        query = select(TestAttempt).options(
            joinedload(TestAttempt.user),
            joinedload(TestAttempt.test)
        ).where(TestAttempt.user_id == user_id)

        if test_id is not None:
            query = query.where(TestAttempt.test_id == test_id)

        query = query.order_by(TestAttempt.started_at.desc())

        result = await session.execute(query)
        return list(result.scalars().unique().all())


async def get_best_attempt(user_id: int, test_id: int, lesson_id: Optional[int] = None) -> Optional[TestAttempt]:
    """Получить лучшую попытку пользователя по тесту (с учётом lesson_id)"""
    async with async_session_maker() as session:
        conditions = [
            TestAttempt.user_id == user_id,
            TestAttempt.test_id == test_id,
            TestAttempt.completed_at.isnot(None)
        ]

        # Фильтруем по lesson_id (None = общий тест, иначе конкретный урок)
        if lesson_id is None:
            conditions.append(TestAttempt.lesson_id.is_(None))
        else:
            conditions.append(TestAttempt.lesson_id == lesson_id)

        result = await session.execute(
            select(TestAttempt)
            .where(and_(*conditions))
            .order_by(TestAttempt.score.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def create_attempt(
    user_id: int,
    test_id: int,
    score: int,
    max_score: int,
    passed: bool,
    answers: dict,
    time_spent_seconds: int = 0,
    lesson_id: Optional[int] = None
) -> TestAttempt:
    """Создать новую попытку (lesson_id=None для общих тестов по серии)"""
    async with async_session_maker() as session:
        attempt = TestAttempt(
            user_id=user_id,
            test_id=test_id,
            lesson_id=lesson_id,
            score=score,
            max_score=max_score,
            passed=passed,
            answers=answers,
            time_spent_seconds=time_spent_seconds,
            completed_at=get_moscow_now()
        )
        session.add(attempt)
        await session.commit()
        await session.refresh(attempt)
        return attempt


async def update_attempt(attempt: TestAttempt) -> TestAttempt:
    """Обновить попытку"""
    async with async_session_maker() as session:
        await session.merge(attempt)
        await session.commit()
        return attempt


# ==================== ЗАКЛАДКИ ====================

async def get_bookmarks_by_user(user_id: int) -> list[Bookmark]:
    """Получить все закладки пользователя (сортировка: новые сверху)"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Bookmark)
            .options(
                joinedload(Bookmark.user),
                joinedload(Bookmark.lesson).joinedload(Lesson.series),
                joinedload(Bookmark.lesson).joinedload(Lesson.book).joinedload(Book.theme),
                joinedload(Bookmark.lesson).joinedload(Lesson.book).joinedload(Book.author),
                joinedload(Bookmark.lesson).joinedload(Lesson.teacher)
            )
            .where(Bookmark.user_id == user_id)
            .order_by(Bookmark.created_at.desc())
        )
        return result.scalars().unique().all()


async def get_bookmark_by_id(bookmark_id: int) -> Bookmark | None:
    """Получить закладку по ID"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Bookmark)
            .options(
                joinedload(Bookmark.lesson).joinedload(Lesson.series),
                joinedload(Bookmark.lesson).joinedload(Lesson.book).joinedload(Book.theme),
                joinedload(Bookmark.lesson).joinedload(Lesson.book).joinedload(Book.author),
                joinedload(Bookmark.lesson).joinedload(Lesson.teacher)
            )
            .where(Bookmark.id == bookmark_id)
        )
        return result.scalar_one_or_none()


async def get_bookmark_by_user_and_lesson(user_id: int, lesson_id: int) -> Bookmark | None:
    """Проверить, есть ли закладка на урок у пользователя"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Bookmark)
            .options(
                joinedload(Bookmark.user),
                joinedload(Bookmark.lesson).joinedload(Lesson.series),
                joinedload(Bookmark.lesson).joinedload(Lesson.book).joinedload(Book.theme),
                joinedload(Bookmark.lesson).joinedload(Lesson.book).joinedload(Book.author),
                joinedload(Bookmark.lesson).joinedload(Lesson.teacher)
            )
            .where(
                Bookmark.user_id == user_id,
                Bookmark.lesson_id == lesson_id
            )
        )
        return result.scalar_one_or_none()


async def count_user_bookmarks(user_id: int) -> int:
    """Подсчитать количество закладок пользователя"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(func.count(Bookmark.id))
            .where(Bookmark.user_id == user_id)
        )
        return result.scalar_one()


async def create_bookmark(user_id: int, lesson_id: int, custom_name: str) -> Bookmark:
    """Создать закладку"""
    async with async_session_maker() as session:
        bookmark = Bookmark(
            user_id=user_id,
            lesson_id=lesson_id,
            custom_name=custom_name,
            created_at=get_moscow_now()
        )
        session.add(bookmark)
        await session.commit()
        await session.refresh(bookmark)
        return bookmark


async def update_bookmark_name(bookmark_id: int, new_name: str) -> Bookmark | None:
    """Переименовать закладку"""
    async with async_session_maker() as session:
        bookmark = await session.get(Bookmark, bookmark_id)
        if bookmark:
            bookmark.custom_name = new_name
            await session.commit()
            await session.refresh(bookmark)
        return bookmark


async def delete_bookmark(bookmark_id: int) -> bool:
    """Удалить закладку"""
    async with async_session_maker() as session:
        bookmark = await session.get(Bookmark, bookmark_id)
        if bookmark:
            await session.delete(bookmark)
            await session.commit()
            return True
        return False


# ==================== ОБРАТНАЯ СВЯЗЬ ====================

async def create_feedback(user_id: int, message_text: str) -> Feedback:
    """Создать обращение обратной связи"""
    async with async_session_maker() as session:
        feedback = Feedback(
            user_id=user_id,
            message_text=message_text,
            status="new",
            created_at=get_moscow_now()
        )
        session.add(feedback)
        await session.commit()
        await session.refresh(feedback)
        return feedback


async def get_feedback_by_id(feedback_id: int) -> Feedback | None:
    """Получить обращение по ID"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Feedback)
            .options(joinedload(Feedback.user))
            .where(Feedback.id == feedback_id)
        )
        return result.scalar_one_or_none()


async def get_all_feedbacks(status: str | None = None) -> list[Feedback]:
    """
    Получить все обращения с фильтром по статусу

    Args:
        status: Фильтр по статусу (new, replied, closed) или None для всех
    """
    async with async_session_maker() as session:
        query = select(Feedback).options(joinedload(Feedback.user))

        if status:
            query = query.where(Feedback.status == status)

        query = query.order_by(Feedback.created_at.desc())

        result = await session.execute(query)
        return result.scalars().unique().all()


async def get_feedbacks_by_user(user_id: int) -> list[Feedback]:
    """Получить все обращения пользователя"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(Feedback)
            .options(joinedload(Feedback.user))
            .where(Feedback.user_id == user_id)
            .order_by(Feedback.created_at.desc())
        )
        return result.scalars().unique().all()


async def count_feedbacks_by_status(status: str) -> int:
    """Подсчитать количество обращений по статусу"""
    async with async_session_maker() as session:
        result = await session.execute(
            select(func.count(Feedback.id))
            .where(Feedback.status == status)
        )
        return result.scalar_one()


async def update_feedback_reply(feedback_id: int, admin_reply: str) -> Feedback | None:
    """Обновить ответ админа на обращение"""
    async with async_session_maker() as session:
        feedback = await session.get(Feedback, feedback_id)
        if feedback:
            feedback.admin_reply = admin_reply
            feedback.status = "replied"
            feedback.replied_at = get_moscow_now()
            await session.commit()
            await session.refresh(feedback)
            return feedback
        return None


async def close_feedback(feedback_id: int) -> Feedback | None:
    """Закрыть обращение"""
    async with async_session_maker() as session:
        feedback = await session.get(Feedback, feedback_id)
        if feedback:
            feedback.status = "closed"
            feedback.closed_at = get_moscow_now()
            await session.commit()
            await session.refresh(feedback)
            return feedback
        return None


async def delete_feedback(feedback_id: int) -> bool:
    """Удалить обращение"""
    async with async_session_maker() as session:
        feedback = await session.get(Feedback, feedback_id)
        if feedback:
            await session.delete(feedback)
            await session.commit()
            return True
        return False
