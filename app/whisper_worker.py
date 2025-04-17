import os
import uuid
import whisper
from math import exp
from pathlib import Path

def transcribe_audio(file_path: str, args: dict) -> list:
    """
    Transcribes an audio file using Whisper and returns:
    [info_summary, transcript_file_path or None]
    """
    model_size = args.get("model", "small")
    language = args.get("language", None)
    temperature = args.get("temperature") or 0.0
    session_id = args.get("session_id", str(uuid.uuid4()))
    user_id = args.get("user_id", '')
    session_start_dttm = args.get("session_start_dttm", '')
    output_type = args.get("output_type", "text")

    BASE_DIR = Path(__file__).resolve().parent.parent
    text_save_dir = BASE_DIR / os.getenv("TRANSCRIPTS_DIR", "data/transcripts")
    os.makedirs(text_save_dir, exist_ok=True)

    print(f"[TRANSCRIBE] Starting transcription {session_id}\nModel={model_size}, lang={language}, temp={temperature}")

    # Load whisper model (this can be cached at higher level too)
    model = whisper.load_model(model_size)

    # Transcribe audio
    result = model.transcribe(
        file_path,
        language=None if language == "auto" else language,
        temperature=temperature
    )

    transcript = result["text"]
    avg_logprob = result["segments"][0]["avg_logprob"] if result.get("segments") else None
    no_speech_prob = result.get("no_speech_prob", None)

    summary = (
        f"Language: {result.get('language')}\n"
        f"Model size: {model_size}\n"
        f"Temperature: {temperature}\n"
        f"Degree of confidence: {round(exp(avg_logprob) * 100, 2)}%\n"
        f"No-speech file probability: {str(round(no_speech_prob * 100, 2)) + '%' if no_speech_prob is not None else 'None'}\n"
    )

    # Decide whether to save full text
    file_path_txt = None
    if output_type == "text" and transcript.strip():
        filename = f"transcript_{user_id}_{session_start_dttm}.txt"
        file_path_txt = os.path.join(text_save_dir, filename)
        with open(file_path_txt, "w", encoding="utf-8") as f:
            f.write(transcript)

    return [summary, file_path_txt]
