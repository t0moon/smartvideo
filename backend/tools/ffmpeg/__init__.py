from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _candidate_dirs() -> list[Path]:
    """Directories that may contain the ffmpeg/ffprobe binaries."""
    dirs: list[Path] = []
    explicit = os.environ.get('FFMPEG_BIN') or ''
    if explicit:
        p = Path(explicit)
        dirs.append(p.parent if p.name.lower().startswith('ffmpeg') else p)

    # WinGet temp install (versioned, e.g. .../WinGet/Gyan.FFmpeg.x/extracted/ffmpeg-x/bin)
    localappdata = os.environ.get('LOCALAPPDATA', '')
    if localappdata:
        wg = Path(localappdata) / 'Temp' / 'WinGet'
        if wg.exists():
            dirs.extend(wg.glob('*/*/ffmpeg-*/bin'))
            dirs.extend(wg.glob('*/*/*/ffmpeg-*/bin'))

    prog = os.environ.get('ProgramFiles', 'C:/Program Files')
    prog86 = os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')
    dirs += [
        Path('C:/ffmpeg/bin'),
        Path(prog) / 'ffmpeg' / 'bin',
        Path(prog86) / 'ffmpeg' / 'bin',
        Path('/opt/homebrew/bin'),
        Path('/usr/local/bin'),
        Path('/usr/bin'),
    ]
    return dirs


def _resolve_bin(name: str) -> str:
    """Return an absolute path to ``ffmpeg``/``ffprobe``.

    Resolves from PATH first, then probes common install locations (WinGet
    temp, Program Files, brew…). As a side effect it also prepends the found
    directory to ``PATH`` so bare-name resolution works everywhere. Falls back
    to the bare name so the subprocess call still surfaces a clear error if
    nothing matches.

    Resolving at *call time* (not import time) is deliberate: the backend
    process that runs a pipeline may have a different PATH than the process
    that first imported this module, and import-time PATH patching alone left
    the render step silently failing with FileNotFoundError.
    """
    explicit = os.environ.get('FFMPEG_BIN' if name == 'ffmpeg' else 'FFPROBE_BIN') or ''
    if explicit and os.path.isfile(explicit):
        return explicit
    found = shutil.which(name)
    if found:
        return found
    for cdir in _candidate_dirs():
        cdir = Path(cdir)
        if not cdir.exists():
            continue
        exe = cdir / (name + '.exe') if os.name == 'nt' else cdir / name
        if exe.exists():
            existing = os.environ.get('PATH', '')
            if str(cdir) not in existing:
                os.environ['PATH'] = str(cdir) + os.pathsep + existing
            print(f'  [FFmpeg] Auto-resolved {name} at: {cdir}')
            return str(exe)
    print(f'  [FFmpeg] WARNING: {name} not found on PATH and no common '
          'install location matched. Set FFMPEG_BIN in .env to fix.')
    return name


def _run_ffmpeg(cmd: list[str], timeout: int = 300) -> tuple[bool, str]:
    """Run an ffmpeg command, return (success, stderr)."""
    if cmd and cmd[0] in ('ffmpeg', 'ffprobe'):
        cmd = [_resolve_bin(cmd[0]), *cmd[1:]]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    except subprocess.TimeoutExpired:
        return False, 'FFmpeg timed out'
    except FileNotFoundError:
        return False, 'FFmpeg not found in PATH'
    except Exception as exc:
        return False, str(exc)


def get_video_duration(path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    ffprobe = _resolve_bin('ffprobe')
    try:
        result = subprocess.run(
            [
                ffprobe, '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip()) if result.stdout.strip() else 0.0
    except Exception:
        return 0.0


def concat_videos(video_paths: list[str], output_path: str) -> str:
    """Concatenate multiple video clips into one.

    Re-encodes to H.264 to guarantee compatibility regardless of
    source codec differences between clips.
    """
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if not video_paths:
        return output_path

    if len(video_paths) == 1:
        import shutil
        shutil.copy2(video_paths[0], output_path)
        return output_path

    # Use concat filter for reliable cross-codec concatenation
    inputs: list[str] = []
    filter_parts: list[str] = []
    for i in range(len(video_paths)):
        inputs.extend(['-i', video_paths[i]])
        filter_parts.append(f'[{i}:v]scale=1280:720,setsar=1[v{i}]')

    concat_inputs = ''.join(f'[v{i}]' for i in range(len(video_paths)))
    filter_complex = ';'.join(filter_parts) + f';{concat_inputs}concat=n={len(video_paths)}:v=1:a=0[outv]'

    cmd = [
        'ffmpeg', '-y',
        *inputs,
        '-filter_complex', filter_complex,
        '-map', '[outv]',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        output_path,
    ]
    ok, err = _run_ffmpeg(cmd)
    if not ok:
        print(f'  [FFmpeg] concat failed, trying demuxer: {err[:200]}')
        return _concat_demuxer(video_paths, output_path)
    print(f'  [FFmpeg] Concatenated {len(video_paths)} clips -> {output_path}')
    return output_path


def _concat_demuxer(video_paths: list[str], output_path: str) -> str:
    """Fallback: concat using demuxer with re-encode."""
    list_file = Path(output_path).with_suffix('.txt')
    list_file.write_text('\n'.join(f"file '{p}'" for p in video_paths), encoding='utf-8')
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', str(list_file),
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        output_path,
    ]
    ok, err = _run_ffmpeg(cmd)
    try:
        list_file.unlink(missing_ok=True)
    except OSError:
        # Safe-delete shims (sandbox) may block unlink; the temp list file is
        # harmless and overwritten on the next run, so ignore the failure.
        pass
    if not ok:
        print(f'  [FFmpeg] demuxer concat also failed: {err[:200]}')
    return output_path


def add_audio_track(video_path: str, audio_path: str, output_path: str) -> str:
    """Replace/add an audio track on a video.

    If the video has no audio stream, this adds one.
    The original video audio (if any) is replaced.
    """
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # The video is the master timeline. Pad the voiceover with silence so the
    # output length is locked to the (longer) video, not truncated to the
    # narration length. `-shortest` then stops at the video duration.
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', audio_path,
        '-filter_complex', '[1:a]apad[a]',
        '-map', '0:v',
        '-map', '[a]',
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        output_path,
    ]
    ok, err = _run_ffmpeg(cmd)
    if not ok:
        print(f'  [FFmpeg] add_audio failed, copying video only: {err[:200]}')
        import shutil
        shutil.copy2(video_path, output_path)
    else:
        print(f'  [FFmpeg] Added audio track -> {output_path}')
    return output_path


def mix_audio_tracks(
    video_path: str,
    voiceover_path: str,
    bgm_path: str | None,
    output_path: str,
    bgm_volume: float = 0.15,
) -> str:
    """Mix voiceover and background music into the video.

    Voiceover is the primary audio at full volume.
    BGM is mixed at a reduced volume (default 15%).
    """
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    inputs = ['-i', video_path, '-i', voiceover_path]
    if bgm_path:
        inputs.extend(['-i', bgm_path])

    if bgm_path:
        # Pad the voiceover to infinity so the mix length is driven by the
        # video (via -shortest), not truncated to the narration length.
        filter_complex = (
            f'[1:a]apad[voice];'
            f'[2:a]volume={bgm_volume}[bgm];'
            f'[voice][bgm]amix=inputs=2:duration=longest:dropout_transition=2[aout]'
        )
        audio_map = '-map', '0:v', '-map', '[aout]'
    else:
        filter_complex = '[1:a]apad[aout]'
        audio_map = '-map', '0:v', '-map', '[aout]'

    cmd = [
        'ffmpeg', '-y',
        *inputs,
        '-filter_complex', filter_complex,
        *audio_map,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        output_path,
    ]
    ok, err = _run_ffmpeg(cmd)
    if not ok:
        print(f'  [FFmpeg] mix_audio failed, trying simple add: {err[:200]}')
        return add_audio_track(video_path, voiceover_path, output_path)
    print(f'  [FFmpeg] Mixed audio -> {output_path}')
    return output_path


def burn_subtitles(video_path: str, srt_path: str, output_path: str) -> str:
    """Burn SRT subtitles into the video (hardcoded, visible on all players)."""
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Escape backslashes and colons for the subtitles filter path (Windows-safe)
    escaped_path = srt_path.replace('\\', '/').replace(':', '\\:')

    vf = f"subtitles='{escaped_path}':force_style='FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,MarginV=30'"

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', vf,
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'copy',
        output_path,
    ]
    ok, err = _run_ffmpeg(cmd)
    if not ok:
        print(f'  [FFmpeg] burn_subtitles failed, skipping: {err[:200]}')
        import shutil
        shutil.copy2(video_path, output_path)
    else:
        print(f'  [FFmpeg] Burned subtitles -> {output_path}')
    return output_path


def concat_audio(audio_paths: list[str], output_path: str) -> str:
    """Concatenate audio files into one continuous track."""
    output_path = str(output_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    if not audio_paths:
        _generate_silence(3.0, output_path)
        return output_path

    if len(audio_paths) == 1:
        import shutil
        shutil.copy2(audio_paths[0], output_path)
        return output_path

    list_file = Path(output_path).with_suffix('.txt')
    list_file.write_text(
        '\n'.join(f"file '{p}'" for p in audio_paths),
        encoding='utf-8',
    )
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat', '-safe', '0',
        '-i', str(list_file),
        '-c:a', 'aac',
        '-b:a', '192k',
        output_path,
    ]
    ok, err = _run_ffmpeg(cmd, timeout=60)
    try:
        list_file.unlink(missing_ok=True)
    except OSError:
        # Safe-delete shims (sandbox) may block unlink; ignore — temp file is
        # overwritten on the next run.
        pass
    if not ok:
        print(f'  [FFmpeg] concat_audio failed: {err[:200]}')
        import shutil
        shutil.copy2(audio_paths[0], output_path)
    return output_path


def _generate_silence(duration: float, output_path: str) -> str:
    """Generate a silent audio file."""
    cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi',
        '-i', f'anullsrc=channel_layout=stereo:sample_rate=44100',
        '-t', f'{duration:.1f}',
        '-q:a', '9',
        output_path,
    ]
    _run_ffmpeg(cmd, timeout=30)
    return output_path


def render_final(
    clip_paths: list[str],
    voiceover_paths: list[str] | None = None,
    srt_path: str | None = None,
    bgm_path: str | None = None,
    output_path: str = '',
    work_dir: str = '',
) -> str:
    """Full render pipeline: concat clips -> add voiceover -> mix BGM -> burn subtitles.

    Args:
        clip_paths: List of video clip file paths to concatenate.
        voiceover_paths: List of narration audio paths (one per clip, same order).
        srt_path: Optional SRT subtitle file to burn in.
        bgm_path: Optional background music file.
        output_path: Final output video path.
        work_dir: Directory for intermediate files.

    Returns:
        Path to the final rendered video.
    """
    work_dir = Path(work_dir) if work_dir else Path(output_path).parent
    work_dir.mkdir(parents=True, exist_ok=True)

    if not clip_paths:
        raise ValueError('No video clips provided for rendering')

    # Step 1: Concatenate video clips
    merged_video = str(work_dir / '_merged.mp4')
    concat_videos(clip_paths, merged_video)

    current = merged_video

    # Step 2: Add voiceover audio
    if voiceover_paths:
        full_voiceover = str(work_dir / '_voiceover.aac')
        concat_audio(voiceover_paths, full_voiceover)

        with_voice = str(work_dir / '_with_voice.mp4')
        if bgm_path and Path(bgm_path).exists():
            mix_audio_tracks(current, full_voiceover, bgm_path, with_voice)
        else:
            add_audio_track(current, full_voiceover, with_voice)
        current = with_voice

    # Step 3: Burn subtitles
    if srt_path and Path(srt_path).exists():
        with_subs = str(work_dir / '_with_subs.mp4')
        burn_subtitles(current, srt_path, with_subs)
        current = with_subs

    # Step 4: Copy to final output
    if current != output_path:
        import shutil
        shutil.copy2(current, output_path)

    # Cleanup intermediate files
    for f in work_dir.glob('_*.mp4'):
        try:
            f.unlink()
        except Exception:
            pass
    for f in work_dir.glob('_*.aac'):
        try:
            f.unlink()
        except Exception:
            pass

    print(f'  [FFmpeg] Final render complete: {output_path}')
    return output_path
