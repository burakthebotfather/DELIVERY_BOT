import logging
import re
import openai
import datetime
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# --- НАСТРОЙКИ ---
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

# --- OpenAI ---
openai.api_key = OPENAI_API_KEY

# --- Логи ---
logging.basicConfig(level=logging.INFO)

# --- Хранилище заявок ---
requests_log = []

# --- Разрешённые чаты и треды ---
ALLOWED_CONTEXTS = [
    {"chat_id": -1002079167705, "thread_id": 7340},
    {"chat_id": -1002387655137, "thread_id": 9},
    {"chat_id": -1002423500927, "thread_id": 4},
    {"chat_id": -1002178818697, "thread_id": 4},
]

# --- Prompt для ИИ ---
PROMPT_TEMPLATE = """
Ты помощник службы доставки. Из текста заявки извлеки:

1. Временной интервал доставки (или фразу: "в ближайшее время", "как можно скорее")
2. Адрес с номером дома
3. Номер телефона
4. Комментарий заказчика (если есть)

Формат ответа:
[временной интервал]
[адрес]
[номер телефона]
Комментарий заказчика: [если есть]

Вот заявка:
{text}
"""

# --- Проверка номера ---
def is_valid_phone(phone: str) -> bool:
    phone = re.sub(r'\D', '', phone)
    return phone.startswith(("375", "8029", "8044", "8033", "8025")) and len(phone) >= 9

# --- Извлечение полей ---
def extract_fields(text: str) -> dict:
    lines = text.strip().split('\n')
    fields = {"interval": "", "address": "", "phone": "", "comment": ""}
    for line in lines:
        if re.search(r'\d{1,2}:\d{2}', line) or 'ближайшее' in line.lower() or 'как можно скорее' in line.lower():
            fields["interval"] = line.strip()
        elif 'Комментарий заказчика:' in line:
            fields["comment"] = line.split('Комментарий заказчика:')[-1].strip()
        elif re.search(r'\+?\d{7,}', line):
            fields["phone"] = re.sub(r'[^\d+]', '', line.strip())
        else:
            fields["address"] = line.strip()
    return fields

# --- Обработка сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat_id = message.chat_id
    thread_id = message.message_thread_id or 0

    if {"chat_id": chat_id, "thread_id": thread_id} not in ALLOWED_CONTEXTS:
        return

    user_text = message.text
    prompt = PROMPT_TEMPLATE.replace("{text}", user_text)

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        parsed = response.choices[0].message.content.strip()
        data = extract_fields(parsed)

        # Проверки
        missing = []
        if not data["address"] or not re.search(r'\d+', data["address"]):
            missing.append("адрес с номером дома")
        if not data["interval"]:
            missing.append("временной интервал")
        if not data["phone"]:
            missing.append("номер телефона")
        elif not is_valid_phone(data["phone"]):
            await message.reply_text(
                "🚫 Заказ не принят в работу! Причина: номер получателя не соответствует региону деятельности службы доставки. "
                "Пожалуйста, пришлите корректный номер телефона в формате +375XXXXXXXXX или своими силами обеспечьте связь водителя с получателем."
            )
            return

        if missing:
            await message.reply_text(
                f"🚫 Заказ не принят в работу! Причина: Не хватает данных для осуществления доставки. "
                f"Пожалуйста, уточните данные и пришлите заявку повторно.\n\nНе хватает: {', '.join(missing)}"
            )
            return

        # Если всё хорошо
        formatted = f"""{data['interval']}
{data['address']}
{data['phone']}
Комментарий заказчика: {data['comment'] or '—'}"""
        await message.reply_text(f"✅ Заказ принят в работу:\n{formatted}")

    except Exception as e:
        logging.error(e)
        await message.reply_text("⚠️ Ошибка при обработке заявки. Попробуйте ещё раз.")

# --- Запуск бота ---
if __name__ == "__main__":
import os
from telegram.ext import Application
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
application = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Бот запущен...")
    app.run_polling()
