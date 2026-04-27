from __future__ import annotations

import os
import re

from langchain_core.messages import AIMessage

from app.artifacts import new_artifact_run_id
from app.config import ARTIFACTS_DIR, VIDEO_PROVIDER
from app.graph.state import AgentState
from app.media.ffmpeg import ffmpeg_available, generate_placeholder_clip
from app.providers.factory import resolve_video_provider
from app.providers.video_base import VideoProvider


def _env_bool(name: str, *, default: bool = True) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def node_generate_clips(state: AgentState) -> dict:
    scenes = state.get("scenes") or []
    if not scenes:
        err = {"step": "video", "message": "scenes is empty."}
        return {"errors": (state.get("errors") or []) + [err]}

    if not ffmpeg_available():
        err = {
            "step": "video",
            "message": "ffmpeg executable not found; please install ffmpeg and add it to PATH.",
        }
        return {"errors": (state.get("errors") or []) + [err]}

    run_id = str(state.get("artifact_run_id") or "").strip() or new_artifact_run_id()
    out_dir = ARTIFACTS_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        provider: VideoProvider | None = resolve_video_provider(out_dir)
    except ValueError as e:
        err = {"step": "video", "message": str(e)}
        return {"errors": (state.get("errors") or []) + [err]}

    clips: dict[str, str] = {}
    palette = ["0x1a1a2e", "0x16213e", "0x0f3460", "0xe94560", "0x533483"]
    used_api = 0
    used_placeholder = 0
    failed_scenes: list[str] = []
    failover_to_placeholder = _env_bool("VIDEO_FAILOVER_TO_PLACEHOLDER", default=True)

    for i, scene in enumerate(scenes):
        sid = str(scene.get("id") or f"scene_{i + 1}")
        safe = re.sub(r"[^0-9A-Za-z._-]+", "_", sid).strip("_") or f"scene_{i + 1}"
        duration = float(scene.get("duration_sec") or 5.0)
        clip_path = out_dir / f"{safe}.mp4"

        vp = str(scene.get("visual_prompt") or "").strip()
        narr = str(scene.get("narration") or "").strip()
        prompt = vp
        if narr:
            prompt = f"{vp}\n\nNarration reference: {narr}".strip() if vp else f"Narration reference: {narr}"
        neg = str(scene.get("negative_prompt") or "").strip()

        if provider is None or not prompt:
            color = palette[i % len(palette)]
            generate_placeholder_clip(clip_path, duration, color=color)
            clips[sid] = str(clip_path.resolve())
            used_placeholder += 1
            continue

        try:
            out = provider.generate(sid, prompt, neg, duration_sec=duration)
        except Exception as e:
            if failover_to_placeholder:
                color = palette[i % len(palette)]
                generate_placeholder_clip(clip_path, duration, color=color)
                clips[sid] = str(clip_path.resolve())
                used_placeholder += 1
                failed_scenes.append(f"{sid}: {e}")
                continue
            err = {"step": "video", "message": f"Scene {sid} video generation failed: {e}"}
            return {"errors": (state.get("errors") or []) + [err]}

        clips[sid] = out
        used_api += 1

    mode = (VIDEO_PROVIDER or "placeholder").lower()
    if provider is None:
        tail = (
            f"Generated {len(clips)} placeholder clips (VIDEO_PROVIDER={mode}, ffmpeg lavfi), "
            f"run_id={run_id}."
        )
    elif used_api and used_placeholder:
        tail = (
            f"Generated {used_api} clips via video provider and {used_placeholder} placeholder clips, "
            f"run_id={run_id}."
        )
    elif used_api:
        tail = f"Generated {used_api} clips via video provider, run_id={run_id}."
    else:
        tail = f"Generated {used_placeholder} placeholder clips, run_id={run_id}."

    if failed_scenes:
        preview = "; ".join(failed_scenes[:2])
        if len(failed_scenes) > 2:
            preview += "; ..."
        tail += f" Fallback applied for failed scenes: {preview}"

    return {
        "artifact_run_id": run_id,
        "clips": clips,
        "messages": [AIMessage(content=tail)],
    }
