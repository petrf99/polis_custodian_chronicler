from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
import asyncio
import os
from pathlib import Path
import datetime
import uuid
from whisper_worker import transcribe_audio
from transcript_duration_estimate import estimate_transcription_time


# FSM: all session states
class FormStates(StatesGroup):
    waiting_language = State()
    waiting_model = State()
    waiting_temperature = State()
    waiting_output_type = State()
    waiting_audio = State()
    waiting_store_decision = State()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

timeout_seconds = int(os.getenv("TIMEOUT_SECONDS", 600))

BASE_DIR = Path(__file__).resolve().parent.parent
audio_save_dir = BASE_DIR / os.getenv("AUDIO_DIR", "data/audio")
os.makedirs(audio_save_dir, exist_ok=True)

# Start button
start_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="✉️ Send file", callback_data="start_session")]
])

# Language selection buttons
language_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="English", callback_data="lang_en"),
     InlineKeyboardButton(text="Russian", callback_data="lang_ru")],
    [InlineKeyboardButton(text="Español", callback_data="lang_es"),
     InlineKeyboardButton(text="Auto", callback_data="lang_auto")]
])

# Whisper model size buttons
model_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="tiny(x0.25)", callback_data="model_tiny"),
     InlineKeyboardButton(text="base(x0.5)", callback_data="model_base")],
    [InlineKeyboardButton(text="small(x1.0)", callback_data="model_small"),
     InlineKeyboardButton(text="medium(x2.0)", callback_data="model_medium"),
     InlineKeyboardButton(text="large(x4.0)", callback_data="model_large")]
])

# Temperature buttons
temp_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="0.0 (accurate)", callback_data="temp_0.0"),
     InlineKeyboardButton(text="0.5 (balanced)", callback_data="temp_0.5")],
    [InlineKeyboardButton(text="1.0 (creative)", callback_data="temp_1.0")],
    [InlineKeyboardButton(text="Use default", callback_data="temp_default")]
])

# Output type buttons
output_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔤 Full Text", callback_data="output_text"),
     InlineKeyboardButton(text="🔄 Info only", callback_data="output_info")]
])

# Store decision buttons
store_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Yes, save it", callback_data="store_yes"),
     InlineKeyboardButton(text="No, don't save", callback_data="store_no")]
])

# Session time out
async def start_timeout_watcher(
    state: FSMContext,
    target_state: State,
    timeout_seconds: int,
    callback_message: types.Message
):
    await asyncio.sleep(timeout_seconds)
    current = await state.get_state()
    if current == target_state.state:
        await state.clear()
        await callback_message.answer(
            "⏳ Session expired due to inactivity.\nPlease start again.",
            reply_markup=start_kb
        )


# Download audio from Telegram
async def download_audio_from_telegram(bot: Bot, file_id: str, save_path: str) -> str:
    file = await bot.get_file(file_id)
    file_path = file.file_path
    destination = os.path.join(save_path, f"{file_id}.ogg")

    await bot.download_file(file_path, destination)
    return destination



# Entry point
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "Welcome to the Polis Chronicler Bot 🏛️\nHere you can send your audio dialogues to transcribe them and record into our Chronicle.\nClick the button below to begin.",
        reply_markup=start_kb
    )

# Prevent users from spamming random messages outside the flow
@dp.message(F.state == default_state)
async def catch_all(message: types.Message):
    await message.reply("Please use the button 'Send file' to start a session. Everything else will be ignored. ⛔",
    reply_markup=start_kb
    )

# Session start
@dp.callback_query(F.data == "start_session")
async def start_session(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await callback.answer("You already have an active session. Finish it first. 🔄", show_alert=True)
        return
    session_id = str(uuid.uuid4())
    print(f"[START SESSION] {session_id}")
    await state.update_data(session_id=session_id)
    await state.update_data(session_start_dttm=datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    await state.update_data(user_id=callback.from_user.id)
    await callback.message.answer("Choose the language of your audio:", reply_markup=language_kb)
    await state.set_state(FormStates.waiting_language)

    asyncio.create_task(start_timeout_watcher(state=state, target_state=FormStates.waiting_language, timeout_seconds=timeout_seconds, callback_message=callback.message))


@dp.callback_query(FormStates.waiting_language, F.data.startswith("lang_"))
async def select_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(language=lang)
    await callback.message.answer("Choose the model size (the bigger size - the longer time):", reply_markup=model_kb)
    await state.set_state(FormStates.waiting_model)

    asyncio.create_task(start_timeout_watcher(state=state, target_state=FormStates.waiting_model, timeout_seconds=timeout_seconds, callback_message=callback.message))


@dp.callback_query(FormStates.waiting_model, F.data.startswith("model_"))
async def select_model(callback: types.CallbackQuery, state: FSMContext):
    model = callback.data.split("_")[1]
    await state.update_data(model=model)
    await callback.message.answer(
        "Select temperature (controls transcription creativity):",
        reply_markup=temp_kb
    )
    await state.set_state(FormStates.waiting_temperature)

    asyncio.create_task(start_timeout_watcher(state=state, target_state=FormStates.waiting_temperature, timeout_seconds=timeout_seconds, callback_message=callback.message))


@dp.callback_query(FormStates.waiting_temperature, F.data.startswith("temp_"))
async def select_temperature(callback: types.CallbackQuery, state: FSMContext):
    temp_val = callback.data.split("_")[1]
    temperature = None if temp_val == "default" else float(temp_val)
    await state.update_data(temperature=temperature)
    await callback.message.answer("Choose what you want to receive:", reply_markup=output_kb)
    await state.set_state(FormStates.waiting_output_type)

    asyncio.create_task(start_timeout_watcher(state=state, target_state=FormStates.waiting_output_type, timeout_seconds=timeout_seconds, callback_message=callback.message))


@dp.callback_query(FormStates.waiting_output_type)
async def select_output_type(callback: types.CallbackQuery, state: FSMContext):
    choice = "text" if "text" in callback.data else "info"
    await state.update_data(output_type=choice)
    await callback.message.answer("🆗 Great. Now send me your audio file or voice message.")
    await state.set_state(FormStates.waiting_audio)

    asyncio.create_task(start_timeout_watcher(state=state, target_state=FormStates.waiting_audio, timeout_seconds=timeout_seconds, callback_message=callback.message))

@dp.message(FormStates.waiting_audio, F.voice | F.audio | F.document)
async def receive_audio(message: types.Message, state: FSMContext):
    file = message.voice or message.audio or message.document

    if not file:
        await message.reply("Please send an actual audio file or voice message.")
        return

    if message.document and not message.document.mime_type.startswith("audio/"):
        await message.reply("This doesn't look like an audio file. Only audio formats are supported.")
        return

    await message.reply("✔️ Your file has been received. Do you want to save it to our Chronicle?", reply_markup=store_kb)
    await state.update_data(file_id=file.file_id)
    await state.update_data(chat_id=message.chat.id)
    await state.set_state(FormStates.waiting_store_decision)

    asyncio.create_task(
            start_timeout_watcher(
                state=state,
                target_state=FormStates.waiting_store_decision,
                timeout_seconds=timeout_seconds,
                callback_message=message
            )
        )

@dp.callback_query(FormStates.waiting_store_decision)
async def store_decision(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "store_yes":
        await callback.message.answer("Your file will be saved to the Chronicle. 📄 \nIt's being transcribed. You will be notified once the transcript is done. 🔔")
        await state.update_data(store_decision=True)
    else:
        await callback.message.answer("Okay, file will not be saved. \nIt's being transcribed. You will be notified once the transcript is done. 🔔")
        await state.update_data(store_decision=False)

    data = await state.get_data()
    session_id = data['session_id']
    await bot.send_message(
            chat_id=data['chat_id'],
            text=f"Transcript ID: {session_id}")
    
    # Launch background whisper transcription
    async def run_transcription(data):

        print("[TRANSCRIPT STARTED]", data['session_id'])
        file_path = await download_audio_from_telegram(bot, data["file_id"], save_path=audio_save_dir)
        transcript_dur = estimate_transcription_time(file_path, data['model'])

        await bot.send_message(
            chat_id=data['chat_id'],
            text=f"⏳ Estimated time for transcript {data['session_id']}:\n{transcript_dur} seconds"
        )

        result = await asyncio.to_thread(transcribe_audio, file_path, data)

        await bot.send_message(
            chat_id=data['chat_id'],
            text=f"✅ Done! Here is some info about your transcript 👇\nID: {session_id}\n\n{result[0]}")

        if result[1] is not None:
            await bot.send_document(
            chat_id=data['chat_id'],
            document=types.FSInputFile(result[1]),
            caption=f"Your transcript, Sir 📄\nID: {session_id}\n\nReady for another one:", reply_markup=start_kb
        )
            
        print("[TRANSCRIPT ENDED]", data['session_id'])

    asyncio.create_task(run_transcription(data))
    
    data = await state.get_data()
    print(f"[END SESSION] {data['session_id']}")
    print(f"[SESSION DATA] {data}")

    await state.clear()
    await callback.message.answer("Session ended 🫡. Ready for another one:", reply_markup=start_kb)

# Main loop
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
