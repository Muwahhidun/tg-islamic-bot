-- Создание базы данных
CREATE DATABASE audio_bot;

-- Подключение к базе данных
\c audio_bot;

-- Создание ролей
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    level INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание пользователей
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    role_id INTEGER REFERENCES roles(id) DEFAULT 3,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание тем
CREATE TABLE themes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание авторов книг
CREATE TABLE book_authors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    biography TEXT,
    birth_year INTEGER,
    death_year INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание преподавателей уроков
CREATE TABLE lesson_teachers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    biography TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание книг
CREATE TABLE books (
    id SERIAL PRIMARY KEY,
    theme_id INTEGER REFERENCES themes(id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES book_authors(id),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание уроков
CREATE TABLE lessons (
    id SERIAL PRIMARY KEY,
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
    teacher_id INTEGER REFERENCES lesson_teachers(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    audio_path VARCHAR(500),
    lesson_number INTEGER,
    duration_seconds INTEGER,
    tags VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов для оптимизации
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_lessons_book_id ON lessons(book_id);
CREATE INDEX idx_books_theme_id ON books(theme_id);
CREATE INDEX idx_books_author_id ON books(author_id);
CREATE INDEX idx_lessons_teacher_id ON lessons(teacher_id);
CREATE INDEX idx_themes_active ON themes(is_active);
CREATE INDEX idx_books_active ON books(is_active);
CREATE INDEX idx_lessons_active ON lessons(is_active);
CREATE INDEX idx_lesson_number ON lessons(book_id, lesson_number);
CREATE INDEX idx_book_authors_active ON book_authors(is_active);
CREATE INDEX idx_lesson_teachers_active ON lesson_teachers(is_active);

-- Полный текстовый поиск по урокам
CREATE INDEX idx_lessons_search ON lessons USING gin(to_tsvector('russian', title || ' ' || description || ' ' || COALESCE(tags, '')));

-- Вставка начальных данных для ролей
INSERT INTO roles (name, description, level) VALUES
('admin', 'Главный администратор', 2),
('moderator', 'Модератор', 1),
('user', 'Пользователь', 0);

-- Вставка начальных данных для авторов книг
INSERT INTO book_authors (name, biography, birth_year, death_year) VALUES
('Мухаммад ибн Абдуль-Ваххаб', 'Великий ученый, реформатор Ислама, основатель движения ваххабитов', 1703, 1792),
('Мухаммад ибн Салих аль-Усаймин', 'Известный саудовский ученый, муфтии, специалист по фикху', 1947, 2001),
('Абдуль-Азиз ибн Баз', 'Великий саудовский ученый, бывший великий муфтии Саудовской Аравии', 1910, 1999);

-- Вставка начальных данных для преподавателей уроков
INSERT INTO lesson_teachers (name, biography) VALUES
('Мухаммад Абу Мунира', 'Студент исламских наук, специалист по акыде и сире'),
('Абдуллах ибн Ибрахим', 'Преподаватель исламских наук в медресе'),
('Юсуф аль-Азхари', 'Известный лектор и специалист по фикху');

-- Вставка начальных данных для тем
INSERT INTO themes (name, description, sort_order) VALUES
('Акыда', 'Основы веры и единобожия', 1),
('Сира', 'Жизнь пророка Мухаммада ﷺ', 2),
('Фикх', 'Исламское право и поклонение', 3),
('Адаб', 'Исламский этикет и нравы', 4);

-- Создание функции для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Создание триггеров для автоматического обновления updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_themes_updated_at BEFORE UPDATE ON themes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_book_authors_updated_at BEFORE UPDATE ON book_authors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lesson_teachers_updated_at BEFORE UPDATE ON lesson_teachers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_books_updated_at BEFORE UPDATE ON books
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lessons_updated_at BEFORE UPDATE ON lessons
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();