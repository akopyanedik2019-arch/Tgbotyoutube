import asyncio
import sqlite3
import os
import threading
from datetime import datetime
from flask import Flask
from telethon import TelegramClient, events
from telethon.tl.types import User, Channel

# ====================== FLASK APP ======================
app = Flask(__name__)

@app.route('/')
def health():
    return "Telegram monitor alive and running!", 200

# ====================== ПУТИ К ДАННЫМ ======================
# На free плане — ephemeral storage (в /app или текущая папка)
DATA_PATH = os.getcwd()  # текущая директория
session_file = os.path.join(DATA_PATH, 'message_monitor.session')
db_file = os.path.join(DATA_PATH, 'messages.db')

# ====================== API ======================
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')

if not api_id or not api_hash:
    raise RuntimeError("API_ID и API_HASH обязательны в Secrets!")

# ====================== БАЗА ======================
def init_db():
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_type TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            chat_title TEXT NOT NULL,
            sender_id INTEGER NOT NULL,
            sender_username TEXT,
            sender_full_name TEXT NOT NULL,
            direction TEXT NOT NULL,
            msg_date TEXT NOT NULL,
            msg_time TEXT NOT NULL,
            message_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ====================== TELETHON ======================
client = TelegramClient(session_file, api_id, api_hash)

@client.on(events.NewMessage)
async def message_handler(event):
    chat = await event.get_chat()
    if isinstance(chat, Channel) and getattr(chat, 'broadcast', False):
        return

    sender = await event.get_sender()
    if sender is None and event.out:
        sender = await client.get_me()
    if sender is None or not isinstance(sender, User):
        return

    sender_id = sender.id
    sender_username = sender.username
    sender_full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "(Без имени)"

    if event.is_private:
        chat_type = "private"
        interlocutor = await event.get_chat()
        chat_id = interlocutor.id
        chat_title = f"{interlocutor.first_name or ''} {interlocutor.last_name or ''}".strip()
        if not chat_title:
            chat_title = f"@{interlocutor.username}" if interlocutor.username else str(chat_id)
    else:
        chat_type = "group"
        chat_id = chat.id
        chat_title = getattr(chat, 'title', '') or str(chat_id)

    direction = "outgoing" if event.out else "incoming"
    msg_date = event.message.date.strftime("%Y-%m-%d")
    msg_time = event.message.date.strftime("%H:%M:%S")
    message_text = event.message.message.strip() if event.message.message else "<Медиа / стикер / голосовое / файл / другое>"

    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''
        INSERT INTO messages 
        (chat_type, chat_id, chat_title, sender_id, sender_username, sender_full_name,
         direction, msg_date, msg_time, message_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (chat_type, chat_id, chat_title, sender_id, sender_username, sender_full_name,
          direction, msg_date, msg_time, message_text))
    conn.commit()
    conn.close()

# ====================== ФОНОВЫЙ ЗАПУСК TELETHON ======================
def run_telethon():
    asyncio.run(main())

async def main():
    await client.start()
    print("Мониторинг запущен (free Render Web Service)")
    await client.run_until_disconnected()

# Запускаем Telethon в отдельном потоке (чтобы не блокировать Flask)
threading.Thread(target=run_telethon, daemon=True).start()

# ====================== FLASK RUN (не нужен, gunicorn из render.yaml) ======================
if __name__ == '__main__':
    app.run()