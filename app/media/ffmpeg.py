from __future__ import annotations

import math
import os
import shutil
import subprocess
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_ffmpeg_exe() -> str:
    """Prefer FFMPEG_PATH/.tools bundle first, fallback to PATH ffmpeg."""
    env = (os.getenv("FFMPEG_PATH") or "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return str(p.resolve())
    for candidate in sorted(_PROJECT_ROOT.glob(".tools/ffmpeg-*-essentials_build/bin/ffmpeg.exe")):
        return str(candidate.resolve())
    for candidate in _PROJECT_ROOT.glob(".tools/ffmpeg-*-essentials_build/bin/ffmpeg"):
        if candidate.is_file():
            return str(candidate.resolve())
    w = shutil.which("ffmpeg")
    return w if w else "ffmpeg"


def ffmpeg_available() -> bool:
    exe = _resolve_ffmpeg_exe()
    if Path(exe).is_file():
        return True
    return shutil.which("ffmpeg") is not None


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err_tail = (result.stderr or "").strip()[-2000:]
        raise RuntimeError(f"ffmpeg failed ({result.returncode}): {' '.join(cmd)}\n{err_tail}")


def media_has_audio(input_path: Path) -> bool:
    probe = subprocess.run(
        [_resolve_ffmpeg_exe(), "-hide_banner", "-i", str(input_path)],
        capture_output=True,
        text=True,
    )
    text = f"{probe.stderr or ''}\n{probe.stdout or ''}"
    return "Audio:" in text


def transcode_clip_for_concat_copy(input_path: Path, output_path: Path) -> None:
    """Transcode clip for concat/copy and always keep a valid stereo audio track."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_resolve_ffmpeg_exe(), "-y", "-i", str(input_path)]
    if media_has_audio(input_path):
        cmd += ["-map", "0:v:0", "-map", "0:a:0"]
    else:
        cmd += [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
        ]
    cmd += [
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    _run_ffmpeg(cmd)


def generate_placeholder_clip(
    output_path: Path,
    duration_sec: float,
    *,
    width: int = 1280,
    height: int = 720,
    color: str = "0x1a1a2e",
) -> None:
    """Generate placeholder clip with silent stereo audio track."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.5, float(duration_sec))
    cmd = [
        _resolve_ffmpeg_exe(),
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s={width}x{height}:d={dur}",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t",
        str(dur),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-b:a",
        "128k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    _run_ffmpeg(cmd)


def transcode_clip_for_concat(
    input_path: Path,
    output_path: Path,
    *,
    duration_sec: float,
    width: int = 1280,
    height: int = 720,
) -> None:
    """Transcode with scale/pad and keep audio for concat/copy."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.5, float(duration_sec))
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
    cmd = [_resolve_ffmpeg_exe(), "-y", "-i", str(input_path)]
    if media_has_audio(input_path):
        cmd += ["-map", "0:v:0", "-map", "0:a:0"]
    else:
        cmd += [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
        ]
    cmd += [
        "-t",
        str(dur),
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    _run_ffmpeg(cmd)


def _cue_style(cue: str) -> tuple[float, float, float]:
    lc = cue.lower()
    if any(k in lc for k in ("whoosh", "swish", "transition")):
        return 260.0, 0.35, 0.18
    if any(k in lc for k in ("click", "tap", "button")):
        return 1800.0, 0.08, 0.22
    if any(k in lc for k in ("ding", "chime", "bell")):
        return 880.0, 0.20, 0.20
    if any(k in lc for k in ("boom", "impact", "hit")):
        return 120.0, 0.22, 0.25
    return 740.0, 0.12, 0.17


def synthesize_sfx_track(output_path: Path, cues: list[str], duration_sec: float) -> bool:
    clean = [c.strip() for c in cues if (c or "").strip()]
    if not clean:
        return False
    duration = max(0.2, float(duration_sec))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [_resolve_ffmpeg_exe(), "-y"]
    slots = max(0.15, duration / (len(clean) + 1))
    filters: list[str] = []
    for i, cue in enumerate(clean):
        freq, clip_dur, vol = _cue_style(cue)
        clip_dur = min(max(0.05, clip_dur), duration)
        cmd += [
            "-f",
            "lavfi",
            "-t",
            f"{clip_dur:.3f}",
            "-i",
            f"sine=frequency={freq:.2f}:sample_rate=48000",
        ]
        start = min(max(0.0, duration - 0.05), 0.15 + i * slots)
        delay_ms = max(0, int(round(start * 1000.0)))
        fade_out_start = max(0.0, clip_dur - 0.05)
        filters.append(
            f"[{i}:a]volume={vol:.4f},afade=t=in:st=0:d=0.01,"
            f"afade=t=out:st={fade_out_start:.3f}:d=0.05,"
            f"adelay={delay_ms}|{delay_ms}[s{i}]"
        )

    mix_inputs = "".join(f"[s{i}]" for i in range(len(clean)))
    filters.append(
        f"{mix_inputs}amix=inputs={len(clean)}:dropout_transition=0,"
        f"atrim=0:{duration:.3f}[outa]"
    )
    cmd += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "[outa]",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    _run_ffmpeg(cmd)
    return True


def _db_to_linear(db: float) -> float:
    return math.pow(10.0, db / 20.0)


def mux_clip_audio(
    input_video: Path,
    output_video: Path,
    *,
    narration_audio: Path | None = None,
    sfx_audio: Path | None = None,
    duration_sec: float | None = None,
    narration_gain_db: float = 2.0,
    sfx_gain_db: float = -2.0,
) -> None:
    output_video.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_resolve_ffmpeg_exe(), "-y", "-i", str(input_video)]
    stream_labels = ["[a0]"]
    filters = ["[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=1.0[a0]"]
    next_idx = 1
    if narration_audio is not None:
        cmd += ["-i", str(narration_audio)]
        dur = f",atrim=0:{max(0.1, float(duration_sec)):.3f}" if duration_sec is not None else ""
        filters.append(
            f"[{next_idx}:a]aformat=sample_rates=48000:channel_layouts=stereo"
            f"{dur},volume={_db_to_linear(narration_gain_db):.4f}[a{next_idx}]"
        )
        stream_labels.append(f"[a{next_idx}]")
        next_idx += 1
    if sfx_audio is not None:
        cmd += ["-i", str(sfx_audio)]
        dur = f",atrim=0:{max(0.1, float(duration_sec)):.3f}" if duration_sec is not None else ""
        filters.append(
            f"[{next_idx}:a]aformat=sample_rates=48000:channel_layouts=stereo"
            f"{dur},volume={_db_to_linear(sfx_gain_db):.4f}[a{next_idx}]"
        )
        stream_labels.append(f"[a{next_idx}]")

    filters.append(
        f"{''.join(stream_labels)}amix=inputs={len(stream_labels)}:normalize=0:dropout_transition=0,"
        "alimiter=limit=0.95[mix]"
    )
    cmd += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "0:v:0",
        "-map",
        "[mix]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-b:a",
        "192k",
        "-shortest",
        str(output_video),
    ]
    _run_ffmpeg(cmd)


def add_bgm_and_master(
    input_video: Path,
    output_video: Path,
    *,
    bgm_path: Path | None = None,
    bgm_gain_db: float = -24.0,
    target_lufs: float = -14.0,
    enable_ducking: bool = True,
    ducking_ratio: float = 10.0,
) -> None:
    output_video.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_resolve_ffmpeg_exe(), "-y", "-i", str(input_video)]
    if bgm_path is not None and bgm_path.is_file():
        cmd += ["-stream_loop", "-1", "-i", str(bgm_path)]
    else:
        cmd += [
            "-f",
            "lavfi",
            "-i",
            "aevalsrc=0.05*sin(2*PI*220*t)+0.04*sin(2*PI*277*t)+0.03*sin(2*PI*330*t):"
            "s=48000:c=2",
        ]

    filters = [
        "[0:a]aformat=sample_rates=48000:channel_layouts=stereo[prog]",
        (
            "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"volume={_db_to_linear(bgm_gain_db):.5f}[bgm]"
        ),
    ]
    bgm_label = "[bgm]"
    if enable_ducking:
        filters.append(
            f"[bgm][prog]sidechaincompress=threshold=0.03:ratio={ducking_ratio:.2f}:"
            "attack=20:release=300[bgmd]"
        )
        bgm_label = "[bgmd]"
    filters.append(
        f"[prog]{bgm_label}amix=inputs=2:normalize=0:dropout_transition=0,"
        f"loudnorm=I={target_lufs:.2f}:TP=-1.5:LRA=11[mix]"
    )
    cmd += [
        "-filter_complex",
        ";".join(filters),
        "-map",
        "0:v:0",
        "-map",
        "[mix]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-b:a",
        "192k",
        "-shortest",
        str(output_video),
    ]
    _run_ffmpeg(cmd)


def concat_videos_copy(paths: list[Path], output_path: Path) -> None:
    """Concat compatible clips losslessly using concat demuxer + stream copy."""
    if not paths:
        raise ValueError("paths is empty")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    list_path = output_path.with_suffix(".concat.txt")
    lines = [f"file '{p.resolve().as_posix()}'" for p in paths]
    list_path.write_text("\n".join(lines), encoding="utf-8")
    cmd = [
        _resolve_ffmpeg_exe(),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        "-c",
        "copy",
        str(output_path),
    ]
    _run_ffmpeg(cmd)
