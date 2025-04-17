# bot.py
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import FSInputFile
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.markdown import hbold
from aiogram import F
import asyncio

# Load token from environment variable
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Init bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

AUDIO_DIR = "./audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(f"Hello, {hbold(message.from_user.first_name)}! Send me a voice or audio message.")

@dp.message(F.voice | F.audio | F.document)
async def handle_audio(message: types.Message):
    file = message.voice or message.audio or message.document
    file_id = file.file_id
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path

    # Save file locally
    file_name = f"{message.message_id}_{file.file_unique_id}.ogg"
    full_path = os.path.join(AUDIO_DIR, file_name)
    await bot.download_file(file_path, full_path)

    await message.reply(f"Audio received and saved as `{file_name}`", parse_mode=ParseMode.MARKDOWN)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
