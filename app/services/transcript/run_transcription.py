# services/transcript.py
from aiogram import Bot, types
import asyncio
import datetime
from jobs.speech2text.whisper_worker import transcribe_audio
from services.transcript.transcript_duration_estimate import estimate_transcription_time
from services.ui_utils.tg_audio_download import download_audio_from_telegram

async def run_transcription(bot: Bot, data: dict, audio_save_dir: str, kb):
    session_id = data['session_id']
    print("[TRANSCRIPT STARTED]", session_id)
    file_path = await download_audio_from_telegram(bot, data["file_id"], save_path=audio_save_dir)
    transcript_dur = estimate_transcription_time(file_path, data['model'])

    await bot.send_message(
        chat_id=data['chat_id'],
        text=f"⏳ Estimated time for transcript:\n\n{str(datetime.timedelta(seconds=transcript_dur))}"
    )

    result = await asyncio.to_thread(transcribe_audio, file_path, data)

    await bot.send_message(
        chat_id=data['chat_id'],
        text=f"✅ Done! Here is some info about your transcript 👇\nID: {session_id}\n\n{result[0]}"
    )

    if result[1] is not None:
        await bot.send_document(
            chat_id=data['chat_id'],
            document=types.FSInputFile(result[1]),
            caption=f"Your transcript, Sir 📄\nID: {session_id}"
        )

    await bot.send_message(
        chat_id=data['chat_id'],
        text=f"\n\nDo you want to save it to our Chronicle? 📜",
        reply_markup=kb
    )

    print("[TRANSCRIPT ENDED]", session_id)
