from flask import Flask
from threading import Thread
import telebot
import time
import json
import os
import requests

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
HF_TOKEN = os.environ.get("HF_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

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
            "repetition_penalty": 1.2,
            "model": "saikrishnagorijala/Friday-V3"
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
            "repetition_penalty": 1.2,
            "model": "saikrishnagorijala/Friday-V3"
        }
    settings[chat_id][key] = value
    save_settings(settings)

def generate_with_hf(prompt, settings):
    url = f"https://router.huggingface.co/hf-inference/models/{settings['model']}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": settings["temperature"],
            "max_new_tokens": settings["max_tokens"],
            "top_p": settings["top_p"],
            "repetition_penalty": settings["repetition_penalty"],
            "do_sample": True,
            "return_full_text": True
        }
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    
    if response.status_code != 200:
        raise Exception(f"API error {response.status_code}: {response.text[:200]}")
    
    result = response.json()
    
    if isinstance(result, list) and len(result) > 0:
        return result[0].get("generated_text", "")
    elif isinstance(result, dict) and "generated_text" in result:
        return result["generated_text"]
    else:
        return str(result)

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
        "/f_generate <текст> - продолжить историю\n"
        "/f_temperature 0.9 - креативность (0.1-2.0)\n"
        "/f_maxtokens 100 - длина (10-500)\n"
        "/f_settings - настройки"
    )

@bot.message_handler(commands=['f_temperature'])
def set_temperature(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "/f_temperature 0.9")
            return
        temp = float(args[1])
        if 0.1 <= temp <= 2.0:
            update_chat_setting(message.chat.id, "temperature", temp)
            bot.reply_to(message, f"✓ Temperature: {temp}")
        else:
            bot.reply_to(message, "0.1 - 2.0")
    except:
        bot.reply_to(message, "Ошибка")

@bot.message_handler(commands=['f_maxtokens'])
def set_max_tokens(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "/f_maxtokens 100")
            return
        tokens = int(args[1])
        if 10 <= tokens <= 500:
            update_chat_setting(message.chat.id, "max_tokens", tokens)
            bot.reply_to(message, f"✓ Max tokens: {tokens}")
        else:
            bot.reply_to(message, "10 - 500")
    except:
        bot.reply_to(message, "Ошибка")

@bot.message_handler(commands=['f_settings'])
def show_settings(message):
    s = get_chat_settings(message.chat.id)
    bot.reply_to(message, 
        f"⚙️ Настройки:\n"
        f"Temperature: {s['temperature']}\n"
        f"Max tokens: {s['max_tokens']}\n"
        f"Top P: {s['top_p']}\n"
        f"Penalty: {s['repetition_penalty']}\n"
        f"Model: {s['model']}"
    )

@bot.message_handler(commands=['f_generate'])
def generate_text(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "/f_generate Вышел Витёк на крыльцо")
        return
    
    prompt = args[1]
    settings = get_chat_settings(message.chat.id)
    wait_msg = bot.reply_to(message, "⏳ Генерирую...")
    
    try:
        result = generate_with_hf(prompt, settings)
        bot.edit_message_text(result, message.chat.id, wait_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ {str(e)[:300]}", message.chat.id, wait_msg.message_id)

def run_bot():
    print("Bot starting...")
    time.sleep(2)
    bot.remove_webhook()
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == '__main__':
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    app.run(host='0.0.0.0', port=10000)
