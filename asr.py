"""
Speech-to-text using Groq's free-tier hosted Whisper endpoint.
No local GPU needed - fits the "cloud, free-tier" setup.
"""
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def transcribe_audio(audio_file_path: str) -> str:
    """
    Sends an audio file to Groq's Whisper-large-v3 endpoint and returns raw text.
    Note: this does NOT include speaker labels - that requires a diarization
    step (e.g. pyannote.audio) run separately and merged with this output.
    """
    with open(audio_file_path, "rb") as f:
        transcription = _client.audio.transcriptions.create(
            file=(os.path.basename(audio_file_path), f.read()),
            model="whisper-large-v3",
            response_format="text",
        )
    return transcription


def clean_transcript(raw_text: str) -> str:
    """
    Light cleanup pass. Kept intentionally minimal - the LLM in summarize_node
    is robust to disfluencies, so avoid over-engineering this step.
    """
    import re
    text = re.sub(r"\s+", " ", raw_text)
    text = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", text, flags=re.IGNORECASE)  # stutter repeats
    return text.strip()
