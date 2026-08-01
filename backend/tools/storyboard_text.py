"""Render a Storyboard (pydantic model or plain dict) into human-readable text.

Used to give reviewers a readable artifact at the storyboard HITL pause point
instead of dumping raw JSON.  The text is stored alongside the structured
payload so the web / Feishu review cards can display it directly.
"""
from __future__ import annotations

from typing import Any


def storyboard_to_txt(storyboard: Any) -> str:
    if hasattr(storyboard, "model_dump"):
        data = storyboard.model_dump()
    elif isinstance(storyboard, dict):
        data = storyboard
    else:
        return str(storyboard)

    lines: list[str] = []
    lines.append("==== 广告分镜脚本 ====")
    if data.get("style_notes"):
        lines.append(f"风格说明: {data['style_notes']}")
    if data.get("pacing"):
        lines.append(f"节奏: {data['pacing']}")
    lines.append("")

    scenes = data.get("scenes", []) or []
    for i, sc in enumerate(scenes, 1):
        title = sc.get("title") or f"场景 {i}"
        lines.append(f"【场景 {i}】{title}")
        if sc.get("description"):
            lines.append(f"  描述: {sc['description']}")
        if sc.get("duration_sec"):
            lines.append(f"  时长: {sc['duration_sec']}s")

        shots = sc.get("shots", []) or []
        if not shots:
            if sc.get("prompt"):
                lines.append(f"  画面: {sc['prompt']}")
            if sc.get("narration"):
                lines.append(f"  旁白: {sc['narration']}")
        else:
            for j, sh in enumerate(shots, 1):
                desc = sh.get("description") or sh.get("prompt") or ""
                lines.append(f"  镜头 {j}: {desc}")
                cam = " ".join(filter(None, [sh.get("camera", ""), sh.get("camera_motion", "")]))
                if cam:
                    lines.append(f"    运镜: {cam}")
                if sh.get("narration"):
                    lines.append(f"    旁白: {sh['narration']}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"
