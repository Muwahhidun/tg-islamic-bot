"""
Сервис для работы с базой данных
"""
from typing import Optional, List
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.models import (
    User, Role, Theme, BookAuthor, LessonTeacher,
    Book, Lesson, async_session_maker
)


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
            result = await session.execute(
                select(BookAuthor).where(BookAuthor.id == author_id)
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
    async def get_lesson_by_id(lesson_id: int) -> Optional[Lesson]:
        """Получение урока по ID"""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Lesson)
                .options(joinedload(Lesson.teacher), joinedload(Lesson.book).joinedload(Book.author))
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
    series_year: int,
    series_name: str,
    description: str = None,
    audio_file_path: str = None,
    duration_minutes: int = None,
    lesson_number: int = None,
    book_id: int = None,
    teacher_id: int = None,
    tags: str = None,
    is_active: bool = True
) -> Lesson:
    """Создание нового урока"""
    async with async_session_maker() as session:
        lesson = Lesson(
            title=title,
            description=description,
            series_year=series_year,
            series_name=series_name,
            audio_path=audio_file_path,
            duration_seconds=duration_minutes * 60 if duration_minutes else None,
            lesson_number=lesson_number,
            book_id=book_id,
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