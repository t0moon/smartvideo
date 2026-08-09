from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None


def _asr_key() -> str:
    from app.config import AUDIO_TTS_API_KEY
    return (AUDIO_TTS_API_KEY or '').strip()


def _asr_base() -> str:
    from app.config import AUDIO_TTS_BASE_URL
    return (AUDIO_TTS_BASE_URL or 'https://api.siliconflow.cn/v1').rstrip('/')


def _asr_model() -> str:
    from app.config import AUDIO_ASR_MODEL
    return (AUDIO_ASR_MODEL or 'FunAudioLLM/SenseVoiceSmall').strip()


_MIME_BY_EXT = {
    '.mp3': 'audio/mpeg',
    '.wav': 'audio/wav',
    '.m4a': 'audio/mp4',
    '.ogg': 'audio/ogg',
    '.flac': 'audio/flac',
}


def transcribe_audio(
    audio_path: str,
    model: Optional[str] = None,
    language: str = 'auto',
) -> str:
    """Transcribe an audio file to text via SiliconFlow ASR (SenseVoiceSmall).

    Returns the transcript text, or '' on failure / missing key. Degrades
    gracefully so the pipeline never crashes on a transcription hiccup.
    """
    if requests is None:
        print('  [ASR] `requests` not installed; skipping transcription.')
        return ''

    key = _asr_key()
    if not key:
        print('  [ASR] No API key configured; skipping transcription.')
        return ''

    audio_path = str(audio_path)
    if not Path(audio_path).exists():
        print(f'  [ASR] File not found: {audio_path}')
        return ''

    endpoint = f'{_asr_base()}/audio/transcriptions'
    model = model or _asr_model()
    ext = Path(audio_path).suffix.lower()
    mime = _MIME_BY_EXT.get(ext, 'application/octet-stream')

    try:
        with open(audio_path, 'rb') as fh:
            resp = requests.post(
                endpoint,
                headers={'Authorization': f'Bearer {key}'},
                files={'file': (Path(audio_path).name, fh, mime)},
                data={'model': model, 'language': language, 'response_format': 'json'},
                timeout=180,
            )
        resp.raise_for_status()
        payload = resp.json()
        text = payload.get('text', '') if isinstance(payload, dict) else str(payload)
        # SenseVoice may prepend a language/emotion tag like "<|zh|>...". Strip it.
        if text.startswith('<|') and '|>' in text:
            text = text.split('|>', 1)[1]
        text = (text or '').strip()
        print(f'  [ASR] Transcribed {Path(audio_path).name}: {len(text)} chars')
        return text
    except Exception as exc:
        print(f'  [ASR] Transcription failed: {exc}')
        return ''
