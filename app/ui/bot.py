from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import os
from pathlib import Path
import datetime
import uuid
from services.transcript.run_transcription import run_transcription
from services.ui_utils.tg_sess_timeout_watcher import start_timeout_watcher
from ui.create_buttons import create_buttons
from services.db_interaction.save_to_chronicle import save_to_chronicle


# FSM: all session states
class FormStates(StatesGroup):
    waiting_language = State()
    waiting_model = State()
    waiting_temperature = State()
    waiting_output_type = State()
    waiting_audio = State()
    waiting_store_decision = State()

# Set up bot
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Set up some params
timeout_seconds = int(os.getenv("TIMEOUT_SECONDS", 600))
BASE_DIR = Path.cwd().parent #Path(__file__).resolve().parent.parent
audio_save_dir = BASE_DIR / os.getenv("AUDIO_DIR", "data/audio")
os.makedirs(audio_save_dir, exist_ok=True)

# Create buttons
start_kb, language_kb, model_kb, temp_kb, output_kb, store_kb = create_buttons()

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
    await state.update_data(session_start_dttm=datetime.datetime.now().isoformat())
    await state.update_data(user_id=callback.from_user.id)

    await callback.message.answer("Choose the language of your audio:", reply_markup=language_kb)
    await state.set_state(FormStates.waiting_language)

    asyncio.create_task(start_timeout_watcher(state=state, target_state=FormStates.waiting_language, timeout_seconds=timeout_seconds, callback_message=callback.message, start_kb=start_kb))


@dp.callback_query(FormStates.waiting_language, F.data.startswith("lang_"))
async def select_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(language=lang)
    await callback.message.answer("Choose the model size (the bigger size - the longer time):", reply_markup=model_kb)
    await state.set_state(FormStates.waiting_model)

    asyncio.create_task(start_timeout_watcher(state=state, target_state=FormStates.waiting_model, timeout_seconds=timeout_seconds, callback_message=callback.message, start_kb=start_kb))


@dp.callback_query(FormStates.waiting_model, F.data.startswith("model_"))
async def select_model(callback: types.CallbackQuery, state: FSMContext):
    model = callback.data.split("_")[1]
    await state.update_data(model=model)
    await callback.message.answer(
        "Select temperature (controls transcription creativity):",
        reply_markup=temp_kb
    )
    await state.set_state(FormStates.waiting_temperature)

    asyncio.create_task(start_timeout_watcher(state=state, target_state=FormStates.waiting_temperature, timeout_seconds=timeout_seconds, callback_message=callback.message, start_kb=start_kb))


@dp.callback_query(FormStates.waiting_temperature, F.data.startswith("temp_"))
async def select_temperature(callback: types.CallbackQuery, state: FSMContext):
    temp_val = callback.data.split("_")[1]
    temperature = None if temp_val == "default" else float(temp_val)
    await state.update_data(temperature=temperature)
    await callback.message.answer("Choose what you want to receive:", reply_markup=output_kb)
    await state.set_state(FormStates.waiting_output_type)

    asyncio.create_task(start_timeout_watcher(state=state, target_state=FormStates.waiting_output_type, timeout_seconds=timeout_seconds, callback_message=callback.message, start_kb=start_kb))


@dp.callback_query(FormStates.waiting_output_type)
async def select_output_type(callback: types.CallbackQuery, state: FSMContext):
    choice = "text" if "text" in callback.data else "info"
    await state.update_data(output_type=choice)
    await callback.message.answer("🆗 Great. Now send me your audio file or voice message.")
    await state.set_state(FormStates.waiting_audio)

    asyncio.create_task(start_timeout_watcher(state=state, target_state=FormStates.waiting_audio, timeout_seconds=timeout_seconds, callback_message=callback.message, start_kb=start_kb))

@dp.message(FormStates.waiting_audio, F.voice | F.audio | F.document)
async def receive_audio(message: types.Message, state: FSMContext):
    file = message.voice or message.audio or message.document

    if not file:
        await message.reply("Please send an actual audio file or voice message.")
        return

    if message.document and not message.document.mime_type.startswith("audio/"):
        await message.reply("This doesn't look like an audio file. Only audio formats are supported.")
        return

    await message.reply("✔️ Your file has been received. You will be notified once the transcript is done. 🔔")
    await state.update_data(file_id=file.file_id)
    await state.update_data(chat_id=message.chat.id)

    data = await state.get_data()
    session_id = data['session_id']
    await bot.send_message(
            chat_id=data['chat_id'],
            text=f"Transcript ID: {session_id}")

    asyncio.create_task(run_transcription(bot, data, audio_save_dir, store_kb))


    await state.set_state(FormStates.waiting_store_decision)


@dp.callback_query(FormStates.waiting_store_decision)
async def store_decision(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "store_yes":
        await callback.message.answer("Your file will be saved to the Chronicle. 🦾")
        await state.update_data(store_decision=True)
    else:
        await callback.message.answer("Okay, file will not be saved.")
        await state.update_data(store_decision=False)

    
    data = await state.get_data()

    if data["store_decision"]:
        asyncio.create_task(save_to_chronicle(bot, data['session_id'], data['chat_id']))

    print(f"[END SESSION] {data['session_id']}")
    print(f"[SESSION DATA] {data}")

    await state.clear()
    await callback.message.answer("Session ended 🫡. Ready for another one:", reply_markup=start_kb)

# Main loop
async def start_bot():
    await dp.start_polling(bot)
