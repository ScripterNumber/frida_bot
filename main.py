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
    "gpt2-xl": "gpt2-xl",
    "bloom": "bigscience/bloom-560m",
    "rugpt": "sberbank-ai/rugpt3small_based_on_gpt2"
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
            "model": "gpt2"
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
            "model": "gpt2"
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
        },
        "options": {
            "wait_for_model": True
        }
    }
    
    url = f"https://router.huggingface.co/hf-inference/models/{model}"
    response = requests.post(url, headers=headers, json=payload, timeout=120)
    
    if response.status_code == 503:
        raise Exception("Модель загружается, подожди 30 сек")
    
    if response.status_code == 401:
        raise Exception("Ошибка токена. Проверь HF_TOKEN")
    
    if response.status_code != 200:
        raise Exception(f"API {response.status_code}: {response.text[:300]}")
    
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
        "📖 Бот для генерации историй!\n\n"
        "/f_generate <текст> - продолжить\n"
        "/f_model <имя> - сменить модель\n"
        "/f_models - список моделей\n"
        "/f_settings - настройки\n"
        "/f_test - проверить API"
    )

@bot.message_handler(commands=['f_models'])
def list_models(message):
    text = "📋 Модели:\n"
    for key, val in MODELS.items():
        text += f"• {key}\n"
    text += "\n/f_model gpt2"
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
    except:
        bot.reply_to(message, "Ошибка")

@bot.message_handler(commands=['f_settings'])
def show_settings(message):
    s = get_chat_settings(message.chat.id)
    bot.reply_to(message, 
        f"⚙️ Настройки:\n"
        f"Model: {s['model']}\n"
        f"Temperature: {s['temperature']}\n"
        f"Max tokens: {s['max_tokens']}"
    )

@bot.message_handler(commands=['f_generate'])
def generate_text(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "/f_generate Hello world")
        return
    
    prompt = args[1]
    settings = get_chat_settings(message.chat.id)
    wait_msg = bot.reply_to(message, "⏳")
    
    try:
        result = generate_with_hf(prompt, settings)
        if len(result) > 4000:
            result = result[:4000]
        bot.edit_message_text(result, message.chat.id, wait_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ {str(e)[:500]}", message.chat.id, wait_msg.message_id)

@bot.message_handler(commands=['f_test'])
def test_api(message):
    wait_msg = bot.reply_to(message, "🔄 Тест...")
    
    results = []
    
    urls = [
        ("router.huggingface.co", "https://router.huggingface.co/hf-inference/models/gpt2"),
    ]
    
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": "Hello", "parameters": {"max_new_tokens": 5}}
    
    for name, url in urls:
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            results.append(f"{name}: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    results.append(f"✓ {data[0].get('generated_text', '')[:50]}")
            else:
                results.append(f"  {r.text[:100]}")
        except Exception as e:
            results.append(f"{name}: ❌ {str(e)[:50]}")
    
    results.append(f"\nToken: {HF_TOKEN[:10]}..." if HF_TOKEN else "Token: NOT SET!")
    
    bot.edit_message_text("\n".join(results), message.chat.id, wait_msg.message_id)

@bot.message_handler(commands=['f_debug'])
def debug_token(message):
    if HF_TOKEN:
        bot.reply_to(message, f"Token exists: {HF_TOKEN[:8]}...{HF_TOKEN[-4:]}\nLength: {len(HF_TOKEN)}")
    else:
        bot.reply_to(message, "❌ HF_TOKEN не установлен!")

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
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(15)

if __name__ == '__main__':
    bot_thread = Thread(target=run_bot, daemon=True)
    bot_thread.start()
    app.run(host='0.0.0.0', port=10000)
