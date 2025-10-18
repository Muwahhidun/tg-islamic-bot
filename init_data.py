#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных тестовыми данными
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.utils.config import config
from bot.models.database import async_session_maker
from bot.models import User, Role, Theme, BookAuthor, LessonTeacher, Book, Lesson
from sqlalchemy import select


async def create_test_data():
    """Создание тестовых данных в базе данных"""
    
    async with async_session_maker() as session:
        # Проверяем, есть ли уже данные
        result = await session.execute(select(Theme))
        if result.scalars().first():
            print("Тестовые данные уже существуют в базе данных")
            return
        
        # Создаем роли
        admin_role = Role(name="admin", description="Администратор")
        moderator_role = Role(name="moderator", description="Модератор")
        user_role = Role(name="user", description="Пользователь")
        
        session.add_all([admin_role, moderator_role, user_role])
        await session.commit()
        
        # Создаем администратора
        admin_user = User(
            telegram_id=config.admin_telegram_id,
            username="admin",
            first_name="Администратор",
            is_active=True,
            role_id=admin_role.id
        )
        
        session.add(admin_user)
        await session.commit()
        
        # Создаем темы
        themes = [
            Theme(name="Акыда", description="Основы веры и убеждения в исламе", is_active=True),
            Theme(name="Сира", description="Жизнеописание пророка Мухаммада ﷺ", is_active=True),
            Theme(name="Фикх", description="Исламское право и юриспруденция", is_active=True),
            Theme(name="Адаб", description="Исламская этика и нравы", is_active=True),
        ]
        
        session.add_all(themes)
        await session.commit()
        
        # Создаем авторов книг
        authors = [
            BookAuthor(name="Шейх Мухаммад ибн Абдуль-Ваххаб", biography="Основатель движения ваххабитов, известный ученый", is_active=True),
            BookAuthor(name="Имам ан-Навави", biography="Великий ученый-хадисовед и правовед", is_active=True),
            BookAuthor(name="Ибн Таймия", biography="Великий ученый, реформатор исламской мысли", is_active=True),
            BookAuthor(name="Имам аль-Бухари", biography="Составитель сборника достоверных хадисов", is_active=True),
        ]
        
        session.add_all(authors)
        await session.commit()
        
        # Создаем преподавателей
        teachers = [
            LessonTeacher(name="Абу Мунир", biography="Известный преподаватель исламских наук", is_active=True),
            LessonTeacher(name="Абдуллах ибн Юсуф", biography="Специалист по фикху и хадисам", is_active=True),
        ]
        
        session.add_all(teachers)
        await session.commit()
        
        # Создаем книги
        books = [
            Book(
                name="Четыре правила",
                description="Основы таухида и объяснение шirkа",
                author_id=authors[0].id,
                theme_id=themes[0].id,  # Акыда
                is_active=True
            ),
            Book(
                name="Сады праведных",
                description="Сборник хадисов по различным темам",
                author_id=authors[1].id,
                theme_id=themes[1].id,  # Сира
                is_active=True
            ),
            Book(
                name="Основы таухида",
                description="Фундаментальные принципы единобожия",
                author_id=authors[2].id,
                theme_id=themes[0].id,  # Акыда
                is_active=True
            ),
            Book(
                name="Краткая история пророков",
                description="Сжатое изложение жизней пророков",
                author_id=authors[3].id,
                theme_id=themes[1].id,  # Сира
                is_active=True
            ),
        ]
        
        session.add_all(books)
        await session.commit()
        
        # Создаем уроки
        lessons = [
            # Уроки для книги "Четыре правила"
            Lesson(
                title="Урок 1: Введение в таухид",
                description="Понятие таухида и его важность",
                audio_path="audio/four_rules_lesson1.mp3",
                duration_minutes=30,
                lesson_number=1,
                book_id=books[0].id,
                teacher_id=teachers[0].id,
                is_active=True
            ),
            Lesson(
                title="Урок 2: Знание о Господе миров",
                description="Познание Аллаха через Его знаки",
                audio_path="audio/four_rules_lesson2.mp3",
                duration_minutes=25,
                lesson_number=2,
                book_id=books[0].id,
                teacher_id=teachers[0].id,
                is_active=True
            ),
            Lesson(
                title="Урок 3: Знание об исламе с доказательствами",
                description="Пять столпов ислама и их доказательства",
                audio_path="audio/four_rules_lesson3.mp3",
                duration_minutes=35,
                lesson_number=3,
                book_id=books[0].id,
                teacher_id=teachers[0].id,
                is_active=True
            ),
            Lesson(
                title="Урок 4: Знание о пророке ﷺ",
                description="Жизнь и миссия пророка Мухаммада",
                audio_path="audio/four_rules_lesson4.mp3",
                duration_minutes=40,
                lesson_number=4,
                book_id=books[0].id,
                teacher_id=teachers[0].id,
                is_active=True
            ),
            
            # Уроки для книги "Сады праведных"
            Lesson(
                title="Урок 1: Вступление",
                description="Важность хадисов в жизни мусульманина",
                audio_path="audio/gardens_lesson1.mp3",
                duration_minutes=20,
                lesson_number=1,
                book_id=books[1].id,
                teacher_id=teachers[1].id,
                is_active=True
            ),
            Lesson(
                title="Урок 2: Глава о намерении",
                description="Важность правильного намерения в делах",
                audio_path="audio/gardens_lesson2.mp3",
                duration_minutes=25,
                lesson_number=2,
                book_id=books[1].id,
                teacher_id=teachers[1].id,
                is_active=True
            ),
            
            # Уроки для книги "Основы таухида"
            Lesson(
                title="Урок 1: Определение таухида",
                description="Три вида таухида и их значение",
                audio_path="audio/foundations_lesson1.mp3",
                duration_minutes=45,
                lesson_number=1,
                book_id=books[2].id,
                teacher_id=teachers[0].id,
                is_active=True
            ),
        ]
        
        session.add_all(lessons)
        await session.commit()
        
        print("Тестовые данные успешно добавлены в базу данных")


if __name__ == "__main__":
    asyncio.run(create_test_data())