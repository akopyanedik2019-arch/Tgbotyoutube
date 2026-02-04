import asyncio
import sqlite3
import os
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import User, Channel

# ====================== ПУТИ К ДАННЫМ ======================
# Render монтирует диск в /opt/render/data (из render.yaml)
DATA_PATH = os.getenv('DATA_PATH', '/opt/render/data')
os.makedirs(DATA_PATH, exist_ok=True)

session_file = os.path.join(DATA_PATH, 'message_monitor.session')
db_file = os.path.join(DATA_PATH, 'messages.db')

# ====================== API КРЕДЕНШИАЛЫ ======================
# Обязательно добавь в Render → Environment → Secrets:
# API_ID и API_HASH
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')

if not api_id or not api_hash:
    raise RuntimeError("API_ID и API_HASH должны быть заданы в Environment Variables!")

# ====================== ИНИЦИАЛИЗАЦИЯ БАЗЫ ======================
def init_db():
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_type TEXT NOT NULL,           -- private / group
            chat_id INTEGER NOT NULL,
            chat_title TEXT NOT NULL,
            sender_id INTEGER NOT NULL,
            sender_username TEXT,
            sender_full_name TEXT NOT NULL,
            direction TEXT NOT NULL,           -- incoming / outgoing
            msg_date TEXT NOT NULL,
            msg_time TEXT NOT NULL,
            message_text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ====================== КЛИЕНТ TELETHON ======================
client = TelegramClient(session_file, api_id, api_hash)

# ====================== ОБРАБОТЧИК СООБЩЕНИЙ ======================
@client.on(events.NewMessage)
async def message_handler(event):
    # Исключаем каналы (broadcast), чтобы не тонуть в новостях
    chat = await event.get_chat()
    if isinstance(chat, Channel) and getattr(chat, 'broadcast', False):
        return

    # Получаем отправителя
    sender = await event.get_sender()
    if sender is None and event.out:  # свои сообщения
        sender = await client.get_me()
    if sender is None or not isinstance(sender, User):
        return

    # Данные отправителя
    sender_id = sender.id
    sender_username = sender.username
    sender_full_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()
    if not sender_full_name:
        sender_full_name = "(Без имени)"

    # Тип чата и данные чата
    if event.is_private:
        chat_type = "private"
        interlocutor = await event.get_chat()  # User другого человека
        chat_id = interlocutor.id
        chat_title = f"{interlocutor.first_name or ''} {interlocutor.last_name or ''}".strip()
        if not chat_title:
            chat_title = f"@{interlocutor.username}" if interlocutor.username else str(chat_id)
    else:
        chat_type = "group"
        chat_id = chat.id
        chat_title = getattr(chat, 'title', '') or str(chat_id)

    # Направление
    direction = "outgoing" if event.out else "incoming"

    # Дата и время
    msg_date = event.message.date.strftime("%Y-%m-%d")
    msg_time = event.message.date.strftime("%H:%M:%S")

    # Текст сообщения
    if event.message.message:
        message_text = event.message.message.strip()
    else:
        message_text = "<Медиа / стикер / голосовое / файл / другое>"

    # Запись в базу
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute('''
        INSERT INTO messages 
        (chat_type, chat_id, chat_title, sender_id, sender_username, sender_full_name,
         direction, msg_date, msg_time, message_text)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        chat_type, chat_id, chat_title, sender_id, sender_username, sender_full_name,
        direction, msg_date, msg_time, message_text
    ))
    conn.commit()
    conn.close()

# ====================== ОСНОВНОЙ ЗАПУСК ======================
async def main():
    print("Запуск Telegram мониторинга...")
    await client.start()  # При первом запуске запросит телефон и код (смотри логи Render)
    print("Авторизация успешна. Мониторинг приватов и групп работает 24/7.")
    print(f"Сессия: {session_file}")
    print(f"База сообщений: {db_file}")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())