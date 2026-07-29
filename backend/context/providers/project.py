from __future__ import annotations

from typing import Any

from project.service import ProjectService


class ProjectContextProvider:
    name = 'project'

    def provide(self, project_id: str, run_id: str = 'default') -> dict[str, Any]:
        svc = ProjectService()
        try:
            project = svc.get_project(project_id)
            return {
                'project_id': project.project_id,
                'name': project.name,
                'stage': project.stage.value,
                'workflow_name': project.workflow_name,
                'brief': project.brief,
                'created_at': str(project.created_at),
            }
        except Exception:
            return {'project_id': project_id, 'error': 'Project not found'}
