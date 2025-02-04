import os
import random
import psycopg2
from telebot import types, TeleBot
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup

# Настройки подключения к базе данных
dbname = "english_chat_bot_m_1"
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

# Инициализация состояния памяти
state_storage = StateMemoryStorage()
bot = TeleBot(token_bot, state_storage=state_storage)

known_users = []
user_step = {}

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

# Загрузка состояния из БД
def load_state(user_id):
    cursor.execute("SELECT current_state FROM user_states WHERE user_id=%s", (user_id,))
    result = cursor.fetchone()
    if result:
        return MyStates(result[0])
    else:
        return None

# Функция получения текущего шага пользователя
def get_user_step(uid):
    if uid in user_step:
        return user_step[uid]
    else:
        known_users.append(uid)
        user_step[uid] = 0
        print("Новый пользователь, который еще не использовал /start")
        return 0

# Функция получени слова, получение случайных слов для ответа, создание кнопок и отправки сообщения
def train_word(message):
    cid = message.chat.id
    with conn.cursor() as cursor:
        # Получаем список всех личных слов пользователя
        cursor.execute("SELECT word, translation FROM personal_words WHERE user_id = %s;", (message.from_user.id,))
        personal_results = cursor.fetchall()
        
        # Получаем список всех общих слов
        cursor.execute("SELECT word, translation FROM common_words;")
        common_results = cursor.fetchall()
        
        all_words = personal_results + common_results
        
        if len(all_words) < 4:
            bot.send_message(message.chat.id, "К сожалению, в базе данных недостаточно слов для тренировки. Пожалуйста, добавьте больше слов через команду '/add'.")
            return
        
        # Выбираем 4 случайных слова из общего списка
        random.shuffle(all_words)
        results = all_words[:4]
        
        # Извлекаем правильное слово и его перевод
        target_word, translate = results[0]
        options = [result[0] for result in results] 
        random.shuffle(options) 

    # Формируем кнопки с вариантами ответов
    buttons = [types.KeyboardButton(option) for option in options]

    markup = types.ReplyKeyboardMarkup(row_width=2)
    markup.add(*buttons)

    greeting = f"Выберите перевод слова:\n🇷🇺 {translate}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.translate_word, message.chat.id)
    #save_state(message.from_user.id, MyStates.translate_word.name)

    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['options'] = options

# Команда /start
@bot.message_handler(commands=['start'])
def start_command(message):
    cid = message.chat.id
    if cid not in known_users:
        known_users.append(cid)
        user_step[cid] = 0
        bot.send_message(cid, "Привет 👋 Давай попрактикуемся в английском языке. Тренировки можешь проходить в удобном для себя темпе.")

    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
    #load_state(message.from_user.id)
    train_word(message)

# Обработка нажатия кнопки "Следующее слово"
@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    train_word(message)

# Обработка нажатия кнопки "Добавить слово"
@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    cid = message.chat.id
    user_step[cid] = 1
    msg = bot.reply_to(message, "Введите новое слово 🇺🇸: или напишите \"Отменить\" для отмены действия")
    bot.register_next_step_handler(msg, process_new_word)
    bot.set_state(message.from_user.id, MyStates.another_words, message.chat.id)
    save_state(message.from_user.id, MyStates.another_words.name)
    # print("MyStates.another_words.name - ", MyStates.another_words.name)

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
            cursor.execute("""
            SELECT cast(SUM(counts) AS INT) FROM (SELECT COUNT(*) as counts FROM personal_words
            UNION ALL
            SELECT COUNT(*) as counts FROM common_words
            ) AS total_words;
            """)
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
    with conn.cursor() as cursor:
        cursor.execute("SELECT word FROM personal_words WHERE user_id = %s", (message.from_user.id,))
        words = [row[0] for row in cursor.fetchall()]
    keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=True)
    for word in words:
        button = types.KeyboardButton(f"Удалить {word}")
        keyboard.add(button)
    cancel_button = types.KeyboardButton("Отменить удаление")
    keyboard.add(cancel_button)
    bot.send_message(message.chat.id, "Выберите слово для удаления:", reply_markup=keyboard)
    bot.set_state(message.from_user.id, MyStates.delete_word, message.chat.id)
    save_state(message.from_user.id, MyStates.delete_word.name)
    # print("MyStates.delete_word.name - ", MyStates.delete_word.name)

# Обработка отмены удаления слова
@bot.message_handler(func=lambda message: message.text == "Отменить удаление")
def cancel_deletion(message):
    bot.send_message(message.chat.id, "Удаление отменено.")
    open_buttons(message)

# Обработка удаления слова
@bot.message_handler(func=lambda message: message.text.startswith('Удалить '))  # Проверка начала строки
def handle_delete_word(message):
    word_to_delete = message.text[len('Удалить '):].strip()  # Извлечение названия слова
    with conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM personal_words WHERE word = %s AND user_id = %s;", (word_to_delete, message.from_user.id))
        count = cursor.fetchone()[0]
        if count > 0:
            cursor.execute("DELETE FROM personal_words WHERE word = %s AND user_id = %s;", (word_to_delete, message.from_user.id))
            conn.commit()
            bot.send_message(message.chat.id, f"Слово '{word_to_delete}' успешно удалено!")
            # Открываем кнопки после завершения операции
            open_buttons(message)
        else:
            bot.send_message(message.chat.id, f"Слово для удаления '{word_to_delete}' в базе данных не найдено!")

def open_buttons(message):
    # Формируем кнопки
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons = [next_btn, add_word_btn, delete_word_btn]
    
    # Создаем разметку клавиатуры
    markup = types.ReplyKeyboardMarkup(row_width=2)
    markup.add(*buttons)
    
    # Отправляем сообщение с клавиатурой
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
            hint = f"Неверно! Попробуйте ещё раз.\nПереведите слово 🇷🇺{data['translate_word']}"
            
        bot.send_message(message.chat.id, hint, reply_markup=markup)
        bot.set_state(message.from_user.id, MyStates.target_word_word, message.chat.id)
        save_state(message.from_user.id, MyStates.target_word_word.name)      

# Запуск бесконечного опроса событий
bot.infinity_polling(skip_pending=True)
