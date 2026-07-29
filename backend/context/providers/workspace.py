from __future__ import annotations

from typing import Any

from workspace.manager import WorkspaceManager


class WorkspaceContextProvider:
    name = 'workspace'

    def provide(self, project_id: str, run_id: str = 'default') -> dict[str, Any]:
        mgr = WorkspaceManager()
        runs = mgr.list_runs(project_id)
        artifacts = {}
        for fname in ['video_spec', 'storyboard', 'scenes', 'workflow_state']:
            data = mgr.read_artifact(project_id, run_id, f'{fname}.json')
            if data:
                artifacts[fname] = data
        return {
            'run_id': run_id,
            'total_runs': len(runs),
            'recent_runs': runs[-5:] if runs else [],
            'artifacts': artifacts,
        }
