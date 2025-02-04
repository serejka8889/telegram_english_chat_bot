--Таблица общих слов
CREATE TABLE common_words (
    id SERIAL PRIMARY KEY,
    word TEXT NOT NULL,
    translation TEXT NOT NULL
);
--
CREATE TABLE personal_words (
    id SERIAL PRIMARY KEY,
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    user_id BIGINT NOT NULL
);
-- Таблица хранения состояний
CREATE TABLE user_states (
    user_id BIGINT PRIMARY KEY,
    current_state TEXT
);

-- Добавляем общие слова
INSERT INTO common_words (word, translation) VALUES
('red', 'красный'),
('blue', 'синий'),
('green', 'зеленый'),
('yellow', 'желтый'),
('black', 'черный'),
('white', 'белый'),
('i', 'я'),
('you', 'ты'),
('he', 'он'),
('she', 'она');