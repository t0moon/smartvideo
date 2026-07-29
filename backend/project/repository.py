from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.schemas import Project, ProjectCreate, ProjectStage
from shared.exceptions import ProjectNotFoundError
from app.config import PROJECTS_DIR


class ProjectRepository:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or PROJECTS_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _project_file(self, project_id: str) -> Path:
        return self.base_dir / project_id / 'project.json'

    def create(self, data: ProjectCreate) -> Project:
        project_id = f'proj_{uuid.uuid4().hex[:12]}'
        project_dir = self.base_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc)
        project = Project(
            project_id=project_id,
            name=data.name,
            brief=data.brief,
            workflow_name=data.workflow_name,
            stage=ProjectStage.CREATED,
            created_at=now,
            updated_at=now,
        )
        self._save(project)
        return project

    def get(self, project_id: str) -> Project:
        f = self._project_file(project_id)
        if not f.exists():
            raise ProjectNotFoundError(project_id)
        data = json.loads(f.read_text(encoding='utf-8'))
        return Project.model_validate(data)

    def _save(self, project: Project) -> None:
        f = self._project_file(project.project_id)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(
            project.model_dump_json(indent=2),
            encoding='utf-8',
        )

    def update(self, project_id: str, updates: dict[str, Any]) -> Project:
        project = self.get(project_id)
        for key, value in updates.items():
            if hasattr(project, key):
                setattr(project, key, value)
        project.updated_at = datetime.now(timezone.utc)
        self._save(project)
        return project

    def delete(self, project_id: str) -> None:
        project_dir = self.base_dir / project_id
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir)

    def list_all(self) -> list[Project]:
        projects = []
        for d in self.base_dir.iterdir():
            if d.is_dir():
                f = d / 'project.json'
                if f.exists():
                    try:
                        data = json.loads(f.read_text(encoding='utf-8'))
                        projects.append(Project.model_validate(data))
                    except Exception:
                        continue
        projects.sort(key=lambda p: p.updated_at, reverse=True)
        return projects


