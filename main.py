from flask import Flask
from threading import Thread
import telebot
import time
import json
import os
from huggingface_hub import InferenceClient

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
HF_TOKEN = os.environ.get("HF_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

client = InferenceClient(token=HF_TOKEN)

SETTINGS_FILE = "chat_settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)

def get_chat_settings(chat_id):
    settings = load_settings()
    chat_id = str(chat_id)
    if chat_id not in settings:
        settings[chat_id] = {
            "temperature": 0.9,
            "max_tokens": 100,
            "top_p": 0.95,
            "repetition_penalty": 1.2
        }
        save_settings(settings)
    return settings[chat_id]

def update_chat_setting(chat_id, key, value):
    settings = load_settings()
    chat_id = str(chat_id)
    if chat_id not in settings:
        settings[chat_id] = {
            "temperature": 0.9,
            "max_tokens": 100,
            "top_p": 0.95,
            "repetition_penalty": 1.2
        }
    settings[chat_id][key] = value
    save_settings(settings)

@app.route('/')
def home():
    return "Bot is alive!"

@app.route('/health')
def health():
    return "OK", 200

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message, 
        "Бот для генерации историй!\n\n"
        "Команды:\n"
        "/f_generate <текст> - продолжить историю\n"
        "/f_temperature 0.9 - креативность (0.1-2.0)\n"
        "/f_maxtokens 100 - длина ответа (10-500)\n"
        "/f_topp 0.95 - top_p (0.1-1.0)\n"
        "/f_penalty 1.2 - штраф повторов (1.0-2.0)\n"
        "/f_settings - текущие настройки"
    )

@bot.message_handler(commands=['f_temperature'])
def set_temperature(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "Использование: /f_temperature 0.9")
            return
        temp = float(args[1])
        if 0.1 <= temp <= 2.0:
            update_chat_setting(message.chat.id, "temperature", temp)
            bot.reply_to(message, f"✓ Temperature: {temp}")
        else:
            bot.reply_to(message, "Значение от 0.1 до 2.0")
    except ValueError:
        bot.reply_to(message, "Неверное значение")

@bot.message_handler(commands=['f_maxtokens'])
def set_max_tokens(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "Использование: /f_maxtokens 100")
            return
        tokens = int(args[1])
        if 10 <= tokens <= 500:
            update_chat_setting(message.chat.id, "max_tokens", tokens)
            bot.reply_to(message, f"✓ Max tokens: {tokens}")
        else:
            bot.reply_to(message, "Значение от 10 до 500")
    except ValueError:
        bot.reply_to(message, "Неверное значение")

@bot.message_handler(commands=['f_topp'])
def set_top_p(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "Использование: /f_topp 0.95")
            return
        top_p = float(args[1])
        if 0.1 <= top_p <= 1.0:
            update_chat_setting(message.chat.id, "top_p", top_p)
            bot.reply_to(message, f"✓ Top P: {top_p}")
        else:
            bot.reply_to(message, "Значение от 0.1 до 1.0")
    except ValueError:
        bot.reply_to(message, "Неверное значение")

@bot.message_handler(commands=['f_penalty'])
def set_penalty(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "Использование: /f_penalty 1.2")
            return
        penalty = float(args[1])
        if 1.0 <= penalty <= 2.0:
            update_chat_setting(message.chat.id, "repetition_penalty", penalty)
            bot.reply_to(message, f"✓ Repetition penalty: {penalty}")
        else:
            bot.reply_to(message, "Значение от 1.0 до 2.0")
    except ValueError:
        bot.reply_to(message, "Неверное значение")

@bot.message_handler(commands=['f_settings'])
def show_settings(message):
    s = get_chat_settings(message.chat.id)
    bot.reply_to(message, 
        f"⚙️ Настройки чата:\n\n"
        f"Temperature: {s['temperature']}\n"
        f"Max tokens: {s['max_tokens']}\n"
        f"Top P: {s['top_p']}\n"
        f"Repetition penalty: {s['repetition_penalty']}"
    )

@bot.message_handler(commands=['f_generate'])
def generate_text(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "Использование: /f_generate Вышел Витёк на крыльцо")
        return
    
    prompt = args[1]
    settings = get_chat_settings(message.chat.id)
    
    wait_msg = bot.reply_to(message, "⏳ Генерирую...")
    
    try:
        result = client.text_generation(
            prompt,
            model="ai-forever/rugpt3large_based_on_gpt2",
            temperature=settings["temperature"],
            max_new_tokens=settings["max_tokens"],
            top_p=settings["top_p"],
            repetition_penalty=settings["repetition_penalty"],
            do_sample=True
        )
        
        full_text = prompt + result
        bot.edit_message_text(full_text, message.chat.id, wait_msg.message_id)
        
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: {str(e)[:200]}", message.chat.id, wait_msg.message_id)

@bot.message_handler(commands=['f_models'])
def list_models(message):
    bot.reply_to(message,
        "Доступные модели:\n"
        "• ai-forever/rugpt3large_based_on_gpt2 (по умолчанию)\n"
        "• ai-forever/rugpt3medium_based_on_gpt2\n"
        "• ai-forever/rugpt3small_based_on_gpt2"
    )

def run_bot():
    print("Bot starting...")
    time.sleep(3)
    bot.remove_webhook()
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(10)

if __name__ == '__main__':
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    app.run(host='0.0.0.0', port=10000)
