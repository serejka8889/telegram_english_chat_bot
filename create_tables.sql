-- Таблица общих слов
CREATE TABLE IF NOT EXISTS common_words (
    id SERIAL PRIMARY KEY,
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    UNIQUE (word)
);

-- Таблица персональных слов
CREATE TABLE IF NOT EXISTS personal_words (
    id SERIAL PRIMARY KEY,
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    user_id BIGINT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user_states (user_id)
);

-- Таблица хранения состояний
CREATE TABLE IF NOT EXISTS user_states (
    user_id BIGINT PRIMARY KEY,
    current_state TEXT
);
