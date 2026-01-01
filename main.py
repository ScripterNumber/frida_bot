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
    "gpt2": "gpt2",
    "gpt2-large": "gpt2-large",
    "bloom": "bigscience/bloom-560m",
    "phi": "microsoft/phi-2",
    "qwen": "Qwen/Qwen2-1.5B"
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
            "model": "gpt2"
        }
        save_settings(settings)
    return settings[chat_id]

def update_chat_setting(chat_id, key, value):
    settings = load_settings()
    chat_id = str(chat_id)
    if chat_id not in settings:
        settings[chat_id] = {"temperature": 0.9, "max_tokens": 100, "model": "gpt2"}
    settings[chat_id][key] = value
    save_settings(settings)

def generate_with_hf(prompt, settings):
    from huggingface_hub import InferenceClient
    
    client = InferenceClient(token=HF_TOKEN)
    
    result = client.text_generation(
        prompt,
        model=settings["model"],
        max_new_tokens=settings["max_tokens"],
        temperature=settings["temperature"],
        do_sample=True
    )
    
    return prompt + result

@app.route('/')
def home():
    return "Bot is alive!"

@app.route('/health')
def health():
    return "OK", 200

@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message, 
        "📖 Бот для генерации!\n\n"
        "/f_generate <текст>\n"
        "/f_model <имя>\n"
        "/f_models\n"
        "/f_test"
    )

@bot.message_handler(commands=['f_models'])
def list_models(message):
    text = "📋 Модели:\n"
    for key in MODELS:
        text += f"• {key}\n"
    bot.reply_to(message, text)

@bot.message_handler(commands=['f_model'])
def set_model(message):
    args = message.text.split()
    if len(args) < 2:
        s = get_chat_settings(message.chat.id)
        bot.reply_to(message, f"Текущая: {s['model']}")
        return
    model_key = args[1].lower()
    model = MODELS.get(model_key, args[1])
    update_chat_setting(message.chat.id, "model", model)
    bot.reply_to(message, f"✓ {model}")

@bot.message_handler(commands=['f_temperature'])
def set_temp(message):
    try:
        val = float(message.text.split()[1])
        update_chat_setting(message.chat.id, "temperature", val)
        bot.reply_to(message, f"✓ {val}")
    except:
        bot.reply_to(message, "/f_temperature 0.9")

@bot.message_handler(commands=['f_maxtokens'])
def set_tokens(message):
    try:
        val = int(message.text.split()[1])
        update_chat_setting(message.chat.id, "max_tokens", val)
        bot.reply_to(message, f"✓ {val}")
    except:
        bot.reply_to(message, "/f_maxtokens 100")

@bot.message_handler(commands=['f_settings'])
def show_settings(message):
    s = get_chat_settings(message.chat.id)
    bot.reply_to(message, f"Model: {s['model']}\nTemp: {s['temperature']}\nTokens: {s['max_tokens']}")

@bot.message_handler(commands=['f_generate'])
def generate(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "/f_generate Hello world")
        return
    
    settings = get_chat_settings(message.chat.id)
    wait_msg = bot.reply_to(message, "⏳")
    
    try:
        result = generate_with_hf(args[1], settings)
        bot.edit_message_text(result[:4000], message.chat.id, wait_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ {e}", message.chat.id, wait_msg.message_id)

@bot.message_handler(commands=['f_test'])
def test_api(message):
    wait_msg = bot.reply_to(message, "🔄")
    
    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(token=HF_TOKEN)
        
        result = client.text_generation(
            "Hello",
            model="gpt2",
            max_new_tokens=10
        )
        bot.edit_message_text(f"✅ Работает!\n\nHello{result}", message.chat.id, wait_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ {e}", message.chat.id, wait_msg.message_id)

def run_bot():
    print("Starting...")
    time.sleep(3)
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except:
        pass
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(15)

if __name__ == '__main__':
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    app.run(host='0.0.0.0', port=10000)
