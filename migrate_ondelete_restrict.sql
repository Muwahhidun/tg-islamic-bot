-- Миграция: изменить ondelete для series_id на RESTRICT
-- Применяется к существующей БД

-- 1. Изменить lesson.series_id: SET NULL → RESTRICT
ALTER TABLE lessons
DROP CONSTRAINT IF EXISTS lessons_series_id_fkey;

ALTER TABLE lessons
ADD CONSTRAINT lessons_series_id_fkey
FOREIGN KEY (series_id)
REFERENCES lesson_series(id)
ON DELETE RESTRICT;

-- 2. Изменить test.series_id: CASCADE → RESTRICT
ALTER TABLE tests
DROP CONSTRAINT IF EXISTS tests_series_id_fkey;

ALTER TABLE tests
ADD CONSTRAINT tests_series_id_fkey
FOREIGN KEY (series_id)
REFERENCES lesson_series(id)
ON DELETE RESTRICT;

-- 3. Проверка результата
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
JOIN information_schema.referential_constraints AS rc
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND (tc.table_name = 'lessons' OR tc.table_name = 'tests')
  AND kcu.column_name = 'series_id'
ORDER BY tc.table_name;
