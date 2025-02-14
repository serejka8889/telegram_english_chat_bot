import random
import psycopg2
from telebot import types, TeleBot
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup

# Создать базу данных "english_chat_bot_m_2" в postgres

# Настройки подключения к базе данных
dbname = "english_chat_bot_m_2"
user = "postgres"
password = "123456"
host = "127.0.0.1"
port = "5432"

# Токен бота
token_bot = "" # Добавить свой токен телеграм бота
if token_bot is None:
    raise ValueError("token_bot не задан!")

# Подключение к базе данных
try:
    conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
except Exception as e:
    print(f"Произошла ошибка при подключении к базе данных: {e}")
    exit(1)

cursor = conn.cursor()

# Создание таблиц и заполнение базы данных общими словами
def create_filling_db():
    with conn.cursor() as cursor:

        # Создание таблиц
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS common_words (
            id SERIAL PRIMARY KEY,
            word TEXT NOT NULL,
            translation TEXT NOT NULL,
            UNIQUE (word)
        );
        CREATE TABLE IF NOT EXISTS user_states (
            user_id BIGINT PRIMARY KEY,
            current_state TEXT
        );

        CREATE TABLE IF NOT EXISTS personal_words (
            id SERIAL PRIMARY KEY,
            word TEXT NOT NULL,
            translation TEXT NOT NULL,
            user_id BIGINT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user_states (user_id)
        );
        """)
        conn.commit()

        initial_words = [
            ('red', 'красный'),
            ('blue', 'синий'),
            ('green', 'зеленый'),
            ('yellow', 'желтый'),
            ('black', 'черный'),
            ('white', 'белый'),
            ('i', 'я'),
            ('you', 'ты'),
            ('he', 'он'),
            ('she', 'она' )
        ]
        try:
            cursor.executemany("INSERT INTO common_words (word, translation) VALUES (%s, %s) ON CONFLICT (word) DO NOTHING", initial_words)
            conn.commit()
            print("База данных заполнена начальными данными.")
        except Exception as e:
            print(f"Произошла ошибка при заполнении базы данных: {e}")

create_filling_db()

# Инициализация состояния памяти
state_storage = StateMemoryStorage()
bot = TeleBot(token_bot, state_storage=state_storage)

# Команды
class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово ❌'
    NEXT = 'Следующее слово ⏭'

# Состояния
class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()
    delete_word = State()

# Сохранение состояния в БД
def save_state(user_id, state):
    cursor.execute("INSERT INTO user_states (user_id, current_state) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE SET current_state = EXCLUDED.current_state", (user_id, state))
    conn.commit()

def load_state(user_id):
    cursor.execute("SELECT current_state FROM user_states WHERE user_id=%s", (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        return None

# Старт чат бота - команда /start
@bot.message_handler(commands=['start'])
def start_command(message):
    # Проверка наличия пользователя в базе данных
    cursor.execute("SELECT user_id FROM user_states WHERE user_id = %s", (message.from_user.id,))
    user = cursor.fetchone()
    msg = "Давайте попрактикуемся в английском языке. Тренировки можно проходить в удобном для себя темпе."

    if not user:
        # Если пользователя нет в базе данных, добавляем его
        cursor.execute("INSERT INTO user_states (user_id) VALUES (%s)", (message.from_user.id,))
        conn.commit()
        bot.send_message(message.chat.id, f"👋Добро пожаловать! Вы были успешно добавлены в базу данных.\n\n{msg}")
    else:
        bot.send_message(message.chat.id, f"👋Привет! Рад вас видеть снова.\n\n{msg}")

    # Загружаем текущее состояние пользователя
    state = load_state(message.from_user.id)
    if state:
        bot.set_state(message.from_user.id, state, message.chat.id)
    else:
        bot.set_state(message.from_user.id, "target_word", message.chat.id)

    train_word(message)

# Функция получени слова, получение случайных слов для ответа, создание кнопок и отправки сообщения
def train_word(message):
    with conn.cursor() as cursor:
        # Получаем список всех общих слов
        cursor.execute("SELECT * FROM (SELECT word, translation FROM personal_words WHERE user_id = %s UNION ALL SELECT word, translation FROM common_words) AS result ORDER BY RANDOM() LIMIT 4;", (message.from_user.id,))
        results = cursor.fetchall()
               
        # Извлекаем правильное слово и его перевод
        target_word, translate = results[0]
        options = [result[0] for result in results]

        # Перемешиваем список слов
        random.shuffle(options) 

    # Формируем кнопки с вариантами ответов
    buttons = [types.KeyboardButton(option) for option in options]
    markup = types.ReplyKeyboardMarkup(row_width=2)
    markup.add(*buttons)

    greeting = f"Выберите перевод слова:\n🇷🇺: {translate}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, "translate_word", message.chat.id)
    save_state(message.from_user.id, "translate_word")

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['options'] = options

# Обработка нажатия кнопки "Следующее слово"
@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    bot.set_state(message.from_user.id, "target_word", message.chat.id)
    save_state(message.from_user.id, "target_word")
    train_word(message)

# Обработка нажатия кнопки "Добавить слово"
@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    msg = bot.reply_to(message, "Введите новое слово 🇺🇸: или напишите \"Отменить\" для отмены действия")
    bot.register_next_step_handler(msg, process_new_word)
    bot.set_state(message.from_user.id, "another_words", message.chat.id)
    save_state(message.from_user.id, "another_words")

def process_new_word(message):
    new_word = message.text.strip().lower()
    if new_word == "отменить":
        bot.send_message(message.chat.id, "Добавление слова отменено.")
        open_buttons(message)
        return
    msg = bot.reply_to(message, "Введите перевод для этого слова 🇷🇺:")
    bot.register_next_step_handler(msg, save_translation, new_word=new_word)

# Обработка отмены добавления нового слова
@bot.message_handler(func=lambda message: message.text == "Отменить добавление.")
def cancel_addition(message):
    bot.send_message(message.chat.id, "Добавление слова отменено.")
    open_buttons(message)

# Обработка сохранения перевода нового слова
def save_translation(message, new_word):
    new_translation = message.text.strip().lower()
    with conn.cursor() as cursor:
        # Проверяем, существует ли такое слово в базе
        cursor.execute("SELECT word FROM personal_words WHERE word = %s AND user_id = %s;", (new_word, message.from_user.id))
        word_record = cursor.fetchone()
        if word_record is None:
            cursor.execute("INSERT INTO personal_words (word, translation, user_id) VALUES (%s, %s, %s);", (new_word, new_translation, message.from_user.id))
            conn.commit()
            bot.reply_to(message, "Слово и его перевод сохранены в базе данных.")

            # Подсчитываем общее количество слов, которые изучает пользователь
            cursor.execute("SELECT cast(SUM(counts) AS INT) FROM (SELECT COUNT(*) as counts FROM personal_words WHERE user_id = %s UNION ALL SELECT COUNT(*) as counts FROM common_words) AS total_words;", (message.from_user.id,))
            total_words = cursor.fetchone()[0]

            # Отправляем сообщение с количеством слов
            bot.send_message(message.chat.id, f"Теперь вы изучаете {total_words} слов!")

            # Открываем кнопки после завершения операции
            open_buttons(message)
        else:
            bot.send_message(message.chat.id, f"Такое слово {new_word} уже существует в базе данных!")

# Обработка нажатия кнопки "Удалить слово"
@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def show_delete_options(message):
    mesg = bot.send_message(message.chat.id, "Введите слово 🇺🇸: для удаления или напишите \"Отменить\" для отмены действия:")
    bot.register_next_step_handler(mesg,handle_delete_word)
    bot.set_state(message.from_user.id, "delete_word", message.chat.id)
    save_state(message.from_user.id, "delete_word")

# Обработка отмены удаления слова
@bot.message_handler(func=lambda message: message.text == "Отменить удаление")
def cancel_deletion(message):
    bot.send_message(message.chat.id, "Удаление слова отменено.")
    open_buttons(message)

# Обработка удаления слова
def handle_delete_word(message):
    word_to_delete = message.text.strip().lower()
    if word_to_delete == "отменить":
        bot.send_message(message.chat.id, "Удаление слова отменено.")
        open_buttons(message)
        return

    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM personal_words WHERE word = %s AND user_id = %s returning id;", (word_to_delete, message.from_user.id))
        conn.commit()
        result_del = cursor.fetchone()

        if result_del == None:
            bot.send_message(message.chat.id, f"Слово для удаления '{word_to_delete}' в базе данных не найдено!")
            open_buttons(message)
        else:
            bot.send_message(message.chat.id, f"Слово '{word_to_delete}' успешно удалено!")
            open_buttons(message)          

def open_buttons(message):
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons = [next_btn, add_word_btn, delete_word_btn]
    markup = types.ReplyKeyboardMarkup(row_width=2)
    markup.add(*buttons)
    bot.send_message(message.chat.id, "Что будете делать дальше?", reply_markup=markup)

# Обработка сообщений от пользователя
@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    markup = types.ReplyKeyboardMarkup(row_width=2)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        target_word = data['target_word']
        if text == target_word:
            hint = f"{target_word} -> {data['translate_word']}"
            hint_text = ["Верно!✅", hint]
            hint = "\n".join(hint_text)      
            next_btn = types.KeyboardButton(Command.NEXT)
            add_word_btn = types.KeyboardButton(Command.ADD_WORD)
            delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
            buttons = [next_btn, add_word_btn, delete_word_btn]
            markup.add(*buttons)
        else:
            hint = f"Неверно! Попробуйте ещё раз.\nПереведите слово 🇷🇺: {data['translate_word']}"
            
        bot.send_message(message.chat.id, hint, reply_markup=markup)
        bot.set_state(message.from_user.id, "target_word", message.chat.id)
        save_state(message.from_user.id, "target_word")    

bot.infinity_polling(skip_pending=True)
