import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram import F
import yt_dlp
import aiohttp
import aiofiles
import subprocess

# Токен бота берём из переменной окружения (безопасно для деплоя)
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Укажи BOT_TOKEN в переменных окружения!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Папки для временных файлов
os.makedirs("downloads", exist_ok=True)
os.makedirs("processed", exist_ok=True)

logging.basicConfig(level=logging.INFO)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🔥 Привет, бро! Кидай ссылку на любое видео (Btub, Pornhub, Xvideos, Twitter, OnlyFans и т.д.)\n"
        "Я скачаю, пережму в идеальный 2K 60FPS H.264 + AAC MP4 и дам прямую ссылку на скачивание без лимитов.\n"
        "Работаю с любым порно без цензуры 🚀"
    )

@dp.message(F.text.regexp(r"https?://"))
async def handle_link(message: Message):
    url = message.text.strip()
    chat_id = message.chat.id
    status_msg = await message.answer("⏳ Начинаю обработку... Это может занять 5–30 минут в зависимости от длины видео.")

    try:
        # Шаг 1: Скачивание лучшего качества через yt-dlp
        await status_msg.edit_text("⬇️ Скачиваю видео с сайта...")
        input_file = f"downloads/original_{chat_id}.mp4"
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': input_file,
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(input_file) or os.path.getsize(input_file) == 0:
            await status_msg.edit_text("❌ Не удалось скачать видео. Ссылка битая или сайт блочит.")
            return

        # Шаг 2: Конвертация в 2K 60FPS H.264 + AAC
        await status_msg.edit_text("🎞️ Конвертирую в 2K 60FPS (H.264 + AAC)...")
        output_file = f"processed/video_2k60_{chat_id}.mp4"
        
        ffmpeg_cmd = [
            'ffmpeg', '-i', input_file,
            '-vf', 'scale=2560:1440:force_original_aspect_ratio=decrease,pad=2560:1440:(ow-iw)/2:(oh-ih)/2,fps=60',
            '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart',
            '-y', output_file
        ]
        
        process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            await status_msg.edit_text("❌ Ошибка конвертации ffmpeg.")
            return

        # Шаг 3: Загрузка на anonymousfiles.io и получение прямой ссылки
        await status_msg.edit_text("☁️ Загружаю на файлообменник (прямая ссылка навсегда)...")
        
        upload_url = "https://api.anonymousfiles.io/"
        async with aiohttp.ClientSession() as session:
            async with aiofiles.open(output_file, 'rb') as f:
                data = await f.read()
            async with session.post(upload_url, data=data) as resp:
                if resp.status == 200:
                    direct_link = (await resp.text()).strip()
                    await status_msg.edit_text(
                        f"✅ Готово! Твоё видео в 2K 60FPS:\n\n"
                        f"🔗 Прямая ссылка:\n{direct_link}\n\n"
                        f"Скачивай без ограничений, файл хранится вечно."
                    )
                else:
                    await status_msg.edit_text(f"❌ Ошибка загрузки: {resp.status}")

        # Очистка временных файлов
        if os.path.exists(input_file):
            os.remove(input_file)
        if os.path.exists(output_file):
            os.remove(output_file)

    except Exception as e:
        logging.error(e)
        await status_msg.edit_text(f"💥 Критическая ошибка: {str(e)}")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
