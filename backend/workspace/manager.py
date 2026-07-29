from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import PROJECTS_DIR, ASSETS_DIR


class WorkspaceManager:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or PROJECTS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_run(self, project_id: str, run_id: str | None = None) -> Path:
        run_id = run_id or datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        run_dir = self.base_dir / project_id / 'runs' / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def workspace_dir(self, project_id: str) -> Path:
        d = self.base_dir / project_id / 'workspace'
        d.mkdir(parents=True, exist_ok=True)
        return d

    def artifacts_dir(self, project_id: str, run_id: str) -> Path:
        d = self.base_dir / project_id / 'runs' / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_artifact(self, project_id: str, run_id: str, filename: str, data: Any) -> Path:
        d = self.artifacts_dir(project_id, run_id)
        path = d / filename
        if isinstance(data, (dict, list)):
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        else:
            path.write_text(str(data), encoding='utf-8')
        return path

    def read_artifact(self, project_id: str, run_id: str, filename: str) -> Any:
        path = self.artifacts_dir(project_id, run_id) / filename
        if not path.exists():
            return None
        raw = path.read_text(encoding='utf-8')
        if filename.endswith('.json'):
            return json.loads(raw)
        return raw

    def list_runs(self, project_id: str) -> list[str]:
        runs_dir = self.base_dir / project_id / 'runs'
        if not runs_dir.exists():
            return []
        return sorted([d.name for d in runs_dir.iterdir() if d.is_dir()])

    def cleanup_run(self, project_id: str, run_id: str) -> None:
        run_dir = self.base_dir / project_id / 'runs' / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)

    def save_asset(self, asset_type: str, project_id: str, filename: str, data: Any) -> Path:
        d = ASSETS_DIR / asset_type / project_id
        d.mkdir(parents=True, exist_ok=True)
        path = d / filename
        if isinstance(data, (dict, list)):
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        else:
            path.write_text(str(data), encoding='utf-8')
        return path

