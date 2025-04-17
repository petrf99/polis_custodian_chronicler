from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup, default_state
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
import asyncio
import os
import datetime
import uuid

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

timeout_seconds = os.getenv("TIMEOUT_SECONDS")

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
    [InlineKeyboardButton(text="tiny", callback_data="model_tiny"),
     InlineKeyboardButton(text="base", callback_data="model_base")],
    [InlineKeyboardButton(text="small", callback_data="model_small"),
     InlineKeyboardButton(text="medium", callback_data="model_medium"),
     InlineKeyboardButton(text="large", callback_data="model_large")]
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
    await message.reply("Please use the button 'Send file' to start a session. Everything else will be ignored. ⛔")

# Session start
@dp.callback_query(F.data == "start_session")
async def start_session(callback: types.CallbackQuery, state: FSMContext):
    session_id = str(uuid.uuid4())
    print(f"[START SESSION] {session_id}")
    await state.update_data(session_id=session_id)
    await state.update_data(session_start_dttm=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    await state.update_data(user_id=callback.from_user.id)
    await callback.message.answer("Choose the language of your audio:", reply_markup=language_kb)
    await state.set_state(FormStates.waiting_language)

@dp.callback_query(FormStates.waiting_language, F.data.startswith("lang_"))
async def select_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(language=lang)
    await callback.message.answer("Choose the model size:", reply_markup=model_kb)
    await state.set_state(FormStates.waiting_model)

@dp.callback_query(FormStates.waiting_model, F.data.startswith("model_"))
async def select_model(callback: types.CallbackQuery, state: FSMContext):
    model = callback.data.split("_")[1]
    await state.update_data(model=model)
    await callback.message.answer(
        "Select temperature (controls transcription creativity):",
        reply_markup=temp_kb
    )
    await state.set_state(FormStates.waiting_temperature)

@dp.callback_query(FormStates.waiting_temperature, F.data.startswith("temp_"))
async def select_temperature(callback: types.CallbackQuery, state: FSMContext):
    temp_val = callback.data.split("_")[1]
    temperature = None if temp_val == "default" else float(temp_val)
    await state.update_data(temperature=temperature)
    await callback.message.answer("Choose what you want to receive:", reply_markup=output_kb)
    await state.set_state(FormStates.waiting_output_type)

@dp.callback_query(FormStates.waiting_output_type)
async def select_output_type(callback: types.CallbackQuery, state: FSMContext):
    choice = "text" if "text" in callback.data else "info"
    await state.update_data(output_type=choice)
    await callback.message.answer("Great. Now send me your audio file or voice message.")
    await state.set_state(FormStates.waiting_audio)

    # ⏳ Start timeout countdown
    async def audio_timeout():
        await asyncio.sleep(timeout_seconds)  # 5 minutes
        current_state = await state.get_state()
        if current_state == FormStates.waiting_audio.state:
            await state.clear()
            await callback.message.answer("Session expired due to inactivity ⏳. Please start again.", reply_markup=start_kb)

    asyncio.create_task(audio_timeout())

@dp.message(FormStates.waiting_audio, F.voice | F.audio | F.document)
async def receive_audio(message: types.Message, state: FSMContext):
    file = message.voice or message.audio or message.document

    if not file:
        await message.reply("Please send an actual audio file or voice message. 🛑")
        return

    # Extra check: if it's a document, verify it's audio
    if message.document and not message.document.mime_type.startswith("audio/"):
        await message.reply("This doesn't look like an audio file. Only audio formats are supported. 🎧")
        return

    # Placeholder: you can now trigger whisper_worker here
    await message.reply("Processing your audio... (this is a stub).")
    # After processing:
    await message.answer("Here is your transcription result (stub). \nDo you want to save it?", reply_markup=store_kb)
    await state.set_state(FormStates.waiting_store_decision)

@dp.callback_query(FormStates.waiting_store_decision)
async def store_decision(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "store_yes":
        await callback.message.answer("Saved to the Chronicle. 📄")
    else:
        await callback.message.answer("Okay, not saved.")
    
    data = await state.get_data()
    print(f"[END SESSION] {data['session_id']}")
    print(f"[SESSION DATA] {data}")

    await state.clear()
    await callback.message.answer("Session ended. Ready for another one:", reply_markup=start_kb)

# Main loop
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
