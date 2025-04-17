# whisper_worker.py

import whisper

# Load Whisper model once at module level
model = whisper.load_model("small")  # Options: tiny, base, small, medium, large

def transcribe_audio(file_path: str) -> str:
    """
    Transcribes an audio file using Whisper and returns the text.
    """
    print(f"Transcribing: {file_path}")
    result = model.transcribe(file_path)
    return result