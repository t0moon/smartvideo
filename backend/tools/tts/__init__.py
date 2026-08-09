from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Any

from shared.schemas import Scene

# Resolve ffmpeg/ffprobe to an absolute path so calls work even when the
# launching process has no ffmpeg on its PATH (e.g. a WinGet temp install).
from tools.ffmpeg import _resolve_bin


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
    from app.config import (
        AUDIO_TTS_VOICE, AUDIO_TTS_SPEED, AUDIO_TTS_MODEL, AUDIO_TTS_PROVIDER,
    )

    voice = voice or AUDIO_TTS_VOICE
    speed = speed or AUDIO_TTS_SPEED
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    client = _get_tts_client()
    if client and text.strip():
        try:
            # SiliconFlow TTS (CosyVoice2) does NOT accept OpenAI's `speed`
            # field and identifies voices as `model:voice`, so only forward
            # `speed` to the native OpenAI provider.
            kwargs = {'model': AUDIO_TTS_MODEL, 'voice': voice, 'input': text}
            if (AUDIO_TTS_PROVIDER or 'openai').lower() != 'siliconflow':
                kwargs['speed'] = speed
            response = client.audio.speech.create(**kwargs)
            response.stream_to_file(output_path)
            print(f'  [TTS] Generated: {output_path} ({len(text)} chars)')
            return output_path
        except Exception as exc:
            print(f'  [TTS] API error, using silent fallback: {exc}')

    return _generate_silent_audio(text, output_path)


def _generate_silent_audio(text: str, output_path: str) -> str:
    """Generate a silent audio file whose duration matches the estimated reading time."""
    char_count = len(text)
    duration = max(2.0, min(60.0, char_count / 4.0))

    cmd = [
        _resolve_bin('ffmpeg'), '-y',
        '-f', 'lavfi',
        '-i', f'anullsrc=channel_layout=mono:sample_rate=44100',
        '-t', f'{duration:.1f}',
        '-q:a', '9',
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
    except Exception as exc:
        # Never let a missing/!broken ffmpeg kill the whole stitch. Degrade to
        # "no voiceover for this shot" instead of raising an opaque WinError 2.
        print(f'  [TTS] Silent fallback failed (ffmpeg unavailable): {exc}')
        return None
    print(f'  [TTS] Silent fallback: {output_path} ({duration:.1f}s)')
    return output_path


def generate_narration(
    scenes: list[Scene],
    output_dir: str,
) -> dict[str, str]:
    """Generate TTS narration audio for every shot, in playback order.

    Each shot gets its own audio clip so the final render can align a shot's
    voiceover with its own generated video clip. Returns a dict mapping
    ``shot_id -> audio file path`` (for scenes without shots, the scene_id is
    used as the key instead).

    Insertion order follows scene order then shot order within a scene, which
    matches the clip concatenation order used by the workflow.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_map: dict[str, str] = {}
    idx = 0
    for scene in scenes:
        shots = scene.shots or []
        if not shots:
            # No shots defined: narrate the whole scene as one unit.
            scene_id = scene.scene_id or f'scene_{idx}'
            narration = scene.description or f'Scene {idx + 1}'
            audio_path = str(output_dir / f'narration_{idx:03d}.mp3')
            audio_path = generate_tts(narration, audio_path)
            if audio_path:
                audio_map[scene_id] = audio_path
            idx += 1
            continue

        for shot in shots:
            shot_id = shot.shot_id or f'shot_{idx}'
            narration = shot.narration or shot.description or f'Shot {idx + 1}'
            audio_path = str(output_dir / f'narration_{idx:03d}.mp3')
            audio_path = generate_tts(narration, audio_path)
            if audio_path:
                audio_map[shot_id] = audio_path
            idx += 1

    return audio_map


def get_audio_duration(path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                _resolve_bin('ffprobe'), '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 0.0
    except Exception:
        return 0.0
