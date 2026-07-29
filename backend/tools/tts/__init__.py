from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Any

from shared.schemas import Scene


def _get_tts_client():
    """Get OpenAI TTS client, reusing LLM credentials or dedicated TTS config."""
    from app.config import (
        OPENAI_API_KEY, OPENAI_BASE_URL,
        AUDIO_TTS_API_KEY, AUDIO_TTS_BASE_URL,
    )
    api_key = AUDIO_TTS_API_KEY or OPENAI_API_KEY
    base_url = AUDIO_TTS_BASE_URL or OPENAI_BASE_URL

    if not api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    kwargs = {'api_key': api_key}
    if base_url:
        kwargs['base_url'] = base_url
    return OpenAI(**kwargs)


def generate_tts(
    text: str,
    output_path: str,
    voice: str = '',
    speed: float = 0,
) -> str:
    """Generate a single TTS audio file from text.

    Falls back to a silent audio file (via ffmpeg) when no API key is configured,
    so the pipeline can still produce a complete video in placeholder mode.
    """
    from app.config import AUDIO_TTS_VOICE, AUDIO_TTS_SPEED, AUDIO_TTS_MODEL

    voice = voice or AUDIO_TTS_VOICE
    speed = speed or AUDIO_TTS_SPEED
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    client = _get_tts_client()
    if client and text.strip():
        try:
            response = client.audio.speech.create(
                model=AUDIO_TTS_MODEL,
                voice=voice,
                input=text,
                speed=speed,
            )
            response.stream_to_file(output_path)
            print(f'  [TTS] Generated: {output_path} ({len(text)} chars)')
            return output_path
        except Exception as exc:
            print(f'  [TTS] API error, using silent fallback: {exc}')

    _generate_silent_audio(text, output_path)
    return output_path


def _generate_silent_audio(text: str, output_path: str) -> str:
    """Generate a silent audio file whose duration matches the estimated reading time."""
    char_count = len(text)
    duration = max(2.0, min(60.0, char_count / 4.0))

    cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi',
        '-i', f'anullsrc=channel_layout=mono:sample_rate=44100',
        '-t', f'{duration:.1f}',
        '-q:a', '9',
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)
    print(f'  [TTS] Silent fallback: {output_path} ({duration:.1f}s)')
    return output_path


def generate_narration(
    scenes: list[Scene],
    output_dir: str,
) -> dict[str, str]:
    """Generate TTS narration audio for all scenes.

    Returns a dict mapping scene_id -> audio file path.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_map: dict[str, str] = {}
    for i, scene in enumerate(scenes):
        scene_id = scene.scene_id or f'scene_{i}'
        narration = ''
        if scene.shots:
            narration = ' '.join(s.narration for s in scene.shots if s.narration)
        if not narration:
            narration = scene.description or f'Scene {i + 1}'

        audio_path = str(output_dir / f'narration_{i:03d}.mp3')
        generate_tts(narration, audio_path)
        audio_map[scene_id] = audio_path

    return audio_map


def get_audio_duration(path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 0.0
    except Exception:
        return 0.0
