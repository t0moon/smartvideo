from __future__ import annotations

import shutil
from pathlib import Path

from langchain_core.messages import AIMessage

from app.artifacts import write_artifact_json
from app.config import (
    ARTIFACTS_DIR,
    AUDIO_BGM_DUCKING,
    AUDIO_BGM_ENABLE,
    AUDIO_BGM_GAIN_DB,
    AUDIO_BGM_PATH,
    AUDIO_DUCKING_RATIO,
    AUDIO_ENABLE,
    AUDIO_FAILOPEN,
    AUDIO_TARGET_LUFS,
)
from app.graph.state import AgentState
from app.media.ffmpeg import add_bgm_and_master, concat_videos_copy, ffmpeg_available


def node_stitch_final(state: AgentState) -> dict:
    scenes = state.get("scenes") or []
    clips = state.get("clips") or {}
    run_id = str(state.get("artifact_run_id") or "").strip()
    if not scenes or not clips or not run_id:
        err = {"step": "stitch", "message": "missing scenes/clips/artifact_run_id."}
        return {"errors": (state.get("errors") or []) + [err]}

    if not ffmpeg_available():
        err = {"step": "stitch", "message": "ffmpeg executable not found."}
        return {"errors": (state.get("errors") or []) + [err]}

    ordered_paths: list[Path] = []
    missing: list[str] = []
    for i, scene in enumerate(scenes):
        sid = str(scene.get("id") or f"scene_{i+1}")
        p = clips.get(sid)
        if not p:
            missing.append(sid)
            continue
        ordered_paths.append(Path(p))
    if missing:
        err = {"step": "stitch", "message": f"missing clip files for scenes: {', '.join(missing)}"}
        return {"errors": (state.get("errors") or []) + [err]}
    if not ordered_paths:
        err = {"step": "stitch", "message": "ordered_paths is empty."}
        return {"errors": (state.get("errors") or []) + [err]}

    out_dir = ARTIFACTS_DIR / run_id
    base_path = out_dir / "final.base.mp4"
    final_path = out_dir / "final.mp4"

    concat_videos_copy(ordered_paths, base_path)

    mastering_applied = False
    if AUDIO_ENABLE and AUDIO_BGM_ENABLE:
        bgm_path = Path(AUDIO_BGM_PATH).expanduser() if AUDIO_BGM_PATH else None
        try:
            add_bgm_and_master(
                base_path,
                final_path,
                bgm_path=bgm_path,
                bgm_gain_db=AUDIO_BGM_GAIN_DB,
                target_lufs=AUDIO_TARGET_LUFS,
                enable_ducking=AUDIO_BGM_DUCKING,
                ducking_ratio=AUDIO_DUCKING_RATIO,
            )
            mastering_applied = True
        except Exception as exc:  # noqa: BLE001
            if not AUDIO_FAILOPEN:
                err = {"step": "stitch", "message": f"bgm/mastering failed: {exc}"}
                return {"errors": (state.get("errors") or []) + [err]}

    if not mastering_applied:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(base_path, final_path)

    write_artifact_json(
        run_id,
        "outputs_manifest.json",
        {
            "artifact_run_id": run_id,
            "clips": [p.name for p in ordered_paths],
            "final_video": "final.mp4",
            "final_base_video": "final.base.mp4",
            "mastering_applied": mastering_applied,
        },
    )

    tail = f"stitched final video: {final_path}"
    if mastering_applied:
        tail += " (bgm+ducking+loudness applied)"
    return {
        "final_video_path": str(final_path.resolve()),
        "messages": [AIMessage(content=tail)],
    }
