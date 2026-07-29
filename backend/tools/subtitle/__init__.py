from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.schemas import Scene, Storyboard


def _format_timestamp(seconds: float) -> str:
    """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f'{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}'


def generate_srt(
    scenes: list[Scene],
    output_path: str,
) -> str:
    """Generate an SRT subtitle file from scene narration.

    Each shot's narration becomes one subtitle entry, timed by the shot's
    duration_sec. If a scene has no shots, the scene description is used.
    """
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    entries: list[str] = []
    index = 1
    current_time = 0.0

    for scene in scenes:
        if scene.shots:
            for shot in scene.shots:
                text = shot.narration or shot.description
                if not text:
                    continue
                duration = shot.duration_sec or 3
                start = current_time
                end = current_time + duration
                entries.append(f'{index}')
                entries.append(f'{_format_timestamp(start)} --> {_format_timestamp(end)}')
                entries.append(text)
                entries.append('')
                index += 1
                current_time = end
        else:
            text = scene.description
            if not text:
                continue
            duration = scene.duration_sec or 5
            start = current_time
            end = current_time + duration
            entries.append(f'{index}')
            entries.append(f'{_format_timestamp(start)} --> {_format_timestamp(end)}')
            entries.append(text)
            entries.append('')
            index += 1
            current_time = end

    srt_content = '\n'.join(entries)
    Path(output_path).write_text(srt_content, encoding='utf-8')
    print(f'  [Subtitle] Generated: {output_path} ({index - 1} entries)')
    return output_path


def generate_srt_from_text(
    text: str,
    duration_sec: float,
    output_path: str,
    max_chars_per_line: int = 40,
) -> str:
    """Generate a simple SRT file from a block of text, splitting into segments."""
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    segments = _split_text(text, max_chars_per_line)
    entries: list[str] = []
    index = 1
    seg_duration = duration_sec / max(len(segments), 1)

    for i, seg in enumerate(segments):
        start = i * seg_duration
        end = (i + 1) * seg_duration
        entries.append(f'{index}')
        entries.append(f'{_format_timestamp(start)} --> {_format_timestamp(end)}')
        entries.append(seg)
        entries.append('')
        index += 1

    srt_content = '\n'.join(entries)
    Path(output_path).write_text(srt_content, encoding='utf-8')
    print(f'  [Subtitle] Generated from text: {output_path}')
    return output_path


def _split_text(text: str, max_chars: int) -> list[str]:
    """Split text into subtitle-sized segments by sentence and length."""
    import re
    sentences = re.split(r'[。！？.!?]', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    segments: list[str] = []
    for sent in sentences:
        if len(sent) <= max_chars:
            segments.append(sent)
        else:
            for i in range(0, len(sent), max_chars):
                segments.append(sent[i:i + max_chars])

    return segments if segments else [text]
