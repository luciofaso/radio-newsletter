"""Speech synthesis with Gemini-TTS on Google Cloud (Agent Platform, formerly Vertex AI)."""

import base64
import os
import re
import wave
from pathlib import Path

import requests

API_URL = ("https://aiplatform.googleapis.com/v1/projects/{project}/locations/global"
           "/publishers/google/models/{model}:generateContent")
MAX_CHARS = 3000  # about 3 minutes of audio; a request returns at most about 11 minutes
TIMEOUT = 180
RETRIES = 3
PCM_RATE = 24000  # 24 kHz, 16-bit, mono
COST_PER_MINUTE = 0.03  # gemini-2.5-pro-tts: 25 audio tokens per second at $20 per million

# Seconds of audio generated across all calls of this run.
usage = {"seconds": 0.0}


def _chunks(text: str) -> list[str]:
    """Split text at sentence ends into pieces shorter than MAX_CHARS."""
    chunks, current = [], ""
    for sentence in re.split(r"(?<=[.!?…])\s+", text.strip()):
        if current and len(current) + len(sentence) + 1 > MAX_CHARS:
            chunks.append(current)
            current = ""
        current = f"{current} {sentence}".strip()
    return chunks + [current]


def synthesize(text: str, language_code: str) -> bytes:
    """Return raw PCM audio for the text."""
    style = (Path("prompts") / "voice.md").read_text(encoding="utf-8")
    url = API_URL.format(project=os.environ["GOOGLE_CLOUD_PROJECT"], model=os.environ["TTS_MODEL"])
    audio = b""
    for chunk in _chunks(text):
        for attempt in range(RETRIES):
            try:
                resp = requests.post(
                    url,
                    params={"key": os.environ["GOOGLE_API_KEY"]},
                    json={
                        # The model takes no separate instructions: the style goes before the text.
                        "contents": [{"role": "user", "parts": [{"text": f"{style}\n\nTEXT TO READ:\n{chunk}"}]}],
                        "generationConfig": {
                            "responseModalities": ["AUDIO"],
                            "speechConfig": {
                                "languageCode": language_code,
                                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": os.environ["TTS_VOICE"]}},
                            },
                        },
                    },
                    timeout=TIMEOUT,
                )
                break
            except (requests.Timeout, requests.ConnectionError):
                if attempt == RETRIES - 1:
                    raise
        if not resp.ok:
            raise RuntimeError(f"Google TTS API error ({resp.status_code}): {resp.text[:300]}")
        audio += base64.b64decode(resp.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
    usage["seconds"] += len(audio) / (PCM_RATE * 2)
    return audio


def write_wav(pcm: bytes, path: Path) -> None:
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(PCM_RATE)
        f.writeframes(pcm)
