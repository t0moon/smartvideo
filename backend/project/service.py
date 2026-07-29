from __future__ import annotations

from typing import Any

from shared.schemas import Project, ProjectCreate, ProjectStage
from project.repository import ProjectRepository
from workspace.manager import WorkspaceManager


class ProjectService:
    def __init__(self) -> None:
        self.repo = ProjectRepository()
        self.workspace = WorkspaceManager()

    def create_project(self, name: str, brief: str = '', workflow_name: str = 'product_ad') -> Project:
        data = ProjectCreate(name=name, brief=brief, workflow_name=workflow_name)
        project = self.repo.create(data)
        return project

    def get_project(self, project_id: str) -> Project:
        return self.repo.get(project_id)

    def list_projects(self) -> list[Project]:
        return self.repo.list_all()

    def update_project(self, project_id: str, updates: dict[str, Any]) -> Project:
        return self.repo.update(project_id, updates)

    def delete_project(self, project_id: str) -> None:
        self.repo.delete(project_id)

    def advance_stage(self, project_id: str, stage: ProjectStage) -> Project:
        return self.repo.update(project_id, {'stage': stage})
