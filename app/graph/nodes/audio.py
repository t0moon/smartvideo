from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import httpx
from langchain_core.messages import AIMessage

from app.config import (
    ARTIFACTS_DIR,
    AUDIO_ENABLE,
    AUDIO_FAILOPEN,
    AUDIO_NARRATION_GAIN_DB,
    AUDIO_SFX_ENABLE,
    AUDIO_SFX_GAIN_DB,
    AUDIO_TTS_ENABLE,
    AUDIO_TTS_MODEL,
    AUDIO_TTS_PROVIDER,
    AUDIO_TTS_SPEED,
    AUDIO_TTS_TIMEOUT_SEC,
    AUDIO_TTS_VOICE,
    effective_audio_tts_api_key,
    effective_audio_tts_base_url,
)
from app.graph.state import AgentState
from app.media.ffmpeg import ffmpeg_available, mux_clip_audio, synthesize_sfx_track


def _tts_endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/audio/speech"
    return f"{base}/v1/audio/speech"


def _safe_scene_id(scene_id: str, fallback: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "_", scene_id).strip("_") or fallback


def _extract_shot_sfx_map(template: dict[str, Any]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for shot in template.get("shots") or []:
        if not isinstance(shot, dict):
            continue
        sid = str(shot.get("id") or "").strip()
        if not sid:
            continue
        sfx_block = shot.get("sfx_music")
        if not isinstance(sfx_block, dict):
            continue
        cues = []
        for item in sfx_block.get("sfx") or []:
            txt = str(item or "").strip()
            if txt:
                cues.append(txt)
        if cues:
            mapping[sid] = cues
    return mapping


def _extract_scene_sfx(scene: dict[str, Any], shot_map: dict[str, list[str]]) -> list[str]:
    sid = str(scene.get("id") or "").strip()
    cues = list(shot_map.get(sid) or [])
    raw_extra = scene.get("sfx")
    if isinstance(raw_extra, list):
        cues.extend(str(x or "").strip() for x in raw_extra)
    return [c for c in cues if c]


def _synthesize_openai_tts(text: str, output_path: Path) -> None:
    base_url = effective_audio_tts_base_url()
    api_key = effective_audio_tts_api_key()
    if not base_url or not api_key:
        raise RuntimeError("AUDIO TTS needs API base URL and API key.")
    endpoint = _tts_endpoint(base_url)
    payload = {
        "model": AUDIO_TTS_MODEL,
        "voice": AUDIO_TTS_VOICE,
        "input": text,
        "response_format": "mp3",
        "speed": AUDIO_TTS_SPEED,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(float(AUDIO_TTS_TIMEOUT_SEC), connect=30.0)
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(endpoint, headers=headers, json=payload)
    if resp.status_code >= 400:
        detail = resp.text[:1200] if resp.text else ""
        raise RuntimeError(f"TTS HTTP {resp.status_code}: {detail}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(resp.content)


def _build_tts(text: str, output_path: Path) -> None:
    provider = AUDIO_TTS_PROVIDER
    if provider in ("", "none", "off", "disabled"):
        raise RuntimeError("AUDIO_TTS_PROVIDER is disabled.")
    if provider in ("openai", "openai_speech", "openai_audio"):
        _synthesize_openai_tts(text, output_path)
        return
    raise RuntimeError(f"Unsupported AUDIO_TTS_PROVIDER: {provider}")


def node_generate_audio(state: AgentState) -> dict:
    scenes = state.get("scenes") or []
    clips = state.get("clips") or {}
    run_id = str(state.get("artifact_run_id") or "").strip()
    if not AUDIO_ENABLE:
        return {"messages": [AIMessage(content="Audio stage disabled by AUDIO_ENABLE=0.")]}
    if not scenes or not clips or not run_id:
        err = {"step": "audio", "message": "missing scenes/clips/artifact_run_id."}
        return {"errors": (state.get("errors") or []) + [err]}
    if not ffmpeg_available():
        err = {"step": "audio", "message": "ffmpeg executable not found."}
        return {"errors": (state.get("errors") or []) + [err]}

    fail_open = AUDIO_FAILOPEN
    out_dir = ARTIFACTS_DIR / run_id
    audio_dir = out_dir / "audio"
    shot_sfx_map = _extract_shot_sfx_map(state.get("storyboard_template") or {})
    mixed_clips = dict(clips)
    remixed = 0
    tts_count = 0
    sfx_count = 0
    warnings: list[str] = []

    for i, scene in enumerate(scenes):
        sid = str(scene.get("id") or f"scene_{i+1}")
        safe = _safe_scene_id(sid, f"scene_{i+1}")
        clip_ref = clips.get(sid)
        if not clip_ref:
            msg = f"{sid}: missing clip path."
            if fail_open:
                warnings.append(msg)
                continue
            err = {"step": "audio", "message": msg}
            return {"errors": (state.get("errors") or []) + [err]}

        clip_path = Path(clip_ref)
        if not clip_path.is_file():
            msg = f"{sid}: clip file does not exist: {clip_path}"
            if fail_open:
                warnings.append(msg)
                continue
            err = {"step": "audio", "message": msg}
            return {"errors": (state.get("errors") or []) + [err]}

        narration = str(scene.get("narration") or "").strip()
        duration = max(0.2, float(scene.get("duration_sec") or 5.0))
        sfx_cues = _extract_scene_sfx(scene, shot_sfx_map)

        tts_path: Path | None = None
        if AUDIO_TTS_ENABLE and narration:
            tts_candidate = audio_dir / f"{safe}.tts.mp3"
            try:
                _build_tts(narration, tts_candidate)
                tts_path = tts_candidate
                tts_count += 1
            except Exception as exc:  # noqa: BLE001
                msg = f"{sid}: tts failed: {exc}"
                if fail_open:
                    warnings.append(msg)
                else:
                    err = {"step": "audio", "message": msg}
                    return {"errors": (state.get("errors") or []) + [err]}

        sfx_path: Path | None = None
        if AUDIO_SFX_ENABLE and sfx_cues:
            sfx_candidate = audio_dir / f"{safe}.sfx.wav"
            try:
                if synthesize_sfx_track(sfx_candidate, sfx_cues, duration):
                    sfx_path = sfx_candidate
                    sfx_count += 1
            except Exception as exc:  # noqa: BLE001
                msg = f"{sid}: sfx failed: {exc}"
                if fail_open:
                    warnings.append(msg)
                else:
                    err = {"step": "audio", "message": msg}
                    return {"errors": (state.get("errors") or []) + [err]}

        if tts_path is None and sfx_path is None:
            continue

        mixed_path = out_dir / f"{safe}.mix.mp4"
        try:
            mux_clip_audio(
                clip_path,
                mixed_path,
                narration_audio=tts_path,
                sfx_audio=sfx_path,
                duration_sec=duration,
                narration_gain_db=AUDIO_NARRATION_GAIN_DB,
                sfx_gain_db=AUDIO_SFX_GAIN_DB,
            )
        except Exception as exc:  # noqa: BLE001
            msg = f"{sid}: mix failed: {exc}"
            if fail_open:
                warnings.append(msg)
                continue
            err = {"step": "audio", "message": msg}
            return {"errors": (state.get("errors") or []) + [err]}

        mixed_clips[sid] = str(mixed_path.resolve())
        remixed += 1

    tail = (
        f"Audio stage finished: remixed {remixed}/{len(scenes)} clips "
        f"(tts={tts_count}, sfx={sfx_count})."
    )
    if warnings:
        preview = "; ".join(warnings[:2])
        if len(warnings) > 2:
            preview += "; ..."
        tail += f" Warnings: {preview}"

    return {
        "clips": mixed_clips,
        "messages": [AIMessage(content=tail)],
    }
