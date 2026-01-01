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

MODELS = {
    "gpt2": "openai-community/gpt2",
    "gpt2-large": "openai-community/gpt2-large",
    "gpt2-xl": "openai-community/gpt2-xl",
    "bloom": "bigscience/bloom-560m",
    "bloom-1b": "bigscience/bloom-1b1",
    "mistral": "mistralai/Mistral-7B-v0.1",
    "llama": "meta-llama/Llama-2-7b-hf",
    "rugpt": "ai-forever/rugpt3medium_based_on_gpt2",
    "rugpt-small": "ai-forever/rugpt3small_based_on_gpt2"
}

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
            "model": "openai-community/gpt2"
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
            "model": "openai-community/gpt2"
        }
    settings[chat_id][key] = value
    save_settings(settings)

def generate_with_hf(prompt, settings):
    model = settings["model"]
    
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json"
    }
    
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
    
    url = f"https://api-inference.huggingface.co/models/{model}"
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    
    if response.status_code == 503:
        data = response.json()
        wait_time = data.get("estimated_time", 30)
        raise Exception(f"Модель загружается, подожди {int(wait_time)} сек")
    
    if response.status_code == 404:
        raise Exception(f"Модель {model} не найдена. Используй /f_models")
    
    if response.status_code != 200:
        raise Exception(f"API {response.status_code}: {response.text[:200]}")
    
    result = response.json()
    
    if isinstance(result, list) and len(result) > 0:
        return result[0].get("generated_text", "")
    elif isinstance(result, dict):
        if "generated_text" in result:
            return result["generated_text"]
        if "error" in result:
            raise Exception(result["error"])
    
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
        "📖 Бот для генерации историй ануса!\n\n"
        "/f_generate <текст> - продолжить историю\n"
        "/f_temperature 0.9 - креативность\n"
        "/f_maxtokens 100 - длина\n"
        "/f_model <имя> - сменить модель\n"
        "/f_models - список моделей\n"
        "/f_settings - настройки"
    )

@bot.message_handler(commands=['f_models'])
def list_models(message):
    text = "📋 Доступные модели:\n\n"
    text += "🇬🇧 English:\n"
    text += "• gpt2 (быстрая)\n"
    text += "• gpt2-large\n"
    text += "• gpt2-xl (лучше)\n"
    text += "• bloom\n"
    text += "• bloom-1b\n\n"
    text += "🇷🇺 Русский:\n"
    text += "• rugpt\n"
    text += "• rugpt-small\n\n"
    text += "Пример: /f_model gpt2-xl"
    bot.reply_to(message, text)

@bot.message_handler(commands=['f_model'])
def set_model(message):
    args = message.text.split()
    if len(args) < 2:
        s = get_chat_settings(message.chat.id)
        bot.reply_to(message, f"Текущая: {s['model']}\n\nИспользуй: /f_model gpt2-xl")
        return
    
    model_key = args[1].lower()
    
    if model_key in MODELS:
        model = MODELS[model_key]
    else:
        model = args[1]
    
    update_chat_setting(message.chat.id, "model", model)
    bot.reply_to(message, f"✓ Model: {model}")

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

@bot.message_handler(commands=['f_topp'])
def set_topp(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "/f_topp 0.95")
            return
        val = float(args[1])
        if 0.1 <= val <= 1.0:
            update_chat_setting(message.chat.id, "top_p", val)
            bot.reply_to(message, f"✓ Top P: {val}")
        else:
            bot.reply_to(message, "0.1 - 1.0")
    except:
        bot.reply_to(message, "Ошибка")

@bot.message_handler(commands=['f_penalty'])
def set_penalty(message):
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "/f_penalty 1.2")
            return
        val = float(args[1])
        if 1.0 <= val <= 2.0:
            update_chat_setting(message.chat.id, "repetition_penalty", val)
            bot.reply_to(message, f"✓ Penalty: {val}")
        else:
            bot.reply_to(message, "1.0 - 2.0")
    except:
        bot.reply_to(message, "Ошибка")

@bot.message_handler(commands=['f_settings'])
def show_settings(message):
    s = get_chat_settings(message.chat.id)
    bot.reply_to(message, 
        f"⚙️ Настройки:\n"
        f"Model: {s['model']}\n"
        f"Temperature: {s['temperature']}\n"
        f"Max tokens: {s['max_tokens']}\n"
        f"Top P: {s['top_p']}\n"
        f"Penalty: {s['repetition_penalty']}"
    )

@bot.message_handler(commands=['f_generate'])
def generate_text(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "/f_generate Once upon a time")
        return
    
    prompt = args[1]
    settings = get_chat_settings(message.chat.id)
    wait_msg = bot.reply_to(message, "⏳ Генерирую...")
    
    try:
        result = generate_with_hf(prompt, settings)
        if len(result) > 4000:
            result = result[:4000] + "..."
        bot.edit_message_text(result, message.chat.id, wait_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ {str(e)[:500]}", message.chat.id, wait_msg.message_id)

@bot.message_handler(commands=['f_test'])
def test_api(message):
    wait_msg = bot.reply_to(message, "🔄 Тестирую API...")
    try:
        url = "https://api-inference.huggingface.co/models/openai-community/gpt2"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        payload = {"inputs": "Hello", "parameters": {"max_new_tokens": 10}}
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        bot.edit_message_text(f"Status: {response.status_code}\n{response.text[:500]}", message.chat.id, wait_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ {str(e)}", message.chat.id, wait_msg.message_id)

def run_bot():
    print("Bot starting...")
    time.sleep(3)
    
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except:
        pass
    
    time.sleep(2)
    
    while True:
        try:
            print("Polling started...")
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(15)
            try:
                bot.delete_webhook(drop_pending_updates=True)
            except:
                pass

if __name__ == '__main__':
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    app.run(host='0.0.0.0', port=10000)
