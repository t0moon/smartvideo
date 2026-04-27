"""每次运行的输出目录与 JSON 落盘（时间戳命名，固定在 ARTIFACTS_DIR 下）。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import ARTIFACTS_DIR


def new_artifact_run_id() -> str:
    """本地时间文件夹名，例如 20260421_153045。"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def run_output_dir(run_id: str) -> Path:
    return (ARTIFACTS_DIR / run_id).resolve()


def write_artifact_json(run_id: str, filename: str, data: Any) -> Path | None:
    """写入 ``ARTIFACTS_DIR/<run_id>/<filename>``；失败时返回 None。"""
    if not (run_id or "").strip():
        return None
    d = run_output_dir(run_id.strip())
    try:
        d.mkdir(parents=True, exist_ok=True)
        p = d / filename
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return p
    except OSError:
        return None


def resolve_artifact_run_id(state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """从 state 取 artifact_run_id；若无则新建并返回需合并进 state 的片段。"""
    rid = str(state.get("artifact_run_id") or "").strip()
    if rid:
        return rid, {}
    rid = new_artifact_run_id()
    return rid, {"artifact_run_id": rid}
