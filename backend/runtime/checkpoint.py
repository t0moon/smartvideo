from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from workspace.manager import WorkspaceManager
from runtime.state_machine import WorkflowStateMachine, StageState


class CheckpointManager:
    def __init__(self) -> None:
        self.workspace = WorkspaceManager()

    def save(self, project_id: str, sm: WorkflowStateMachine, run_id: str = 'default') -> str:
        data = {
            'workflow_name': sm.workflow_name,
            'status': sm.status,
            'current_stage_id': sm.current_stage_id,
            'stages': {
                sid: {
                    'state': node.state.value,
                    'config': node.config,
                    'error': node.error,
                    'started_at': str(node.started_at) if node.started_at else None,
                    'completed_at': str(node.completed_at) if node.completed_at else None,
                }
                for sid, node in sm.stages.items()
            },
            'edges': sm.edges,
            'saved_at': datetime.now(timezone.utc).isoformat(),
        }
        path = self.workspace.write_artifact(project_id, run_id, 'checkpoint.json', data)
        return str(path)

    def load(self, project_id: str, run_id: str = 'default') -> WorkflowStateMachine | None:
        data = self.workspace.read_artifact(project_id, run_id, 'checkpoint.json')
        if not data:
            return None

        sm = WorkflowStateMachine(workflow_name=data.get('workflow_name', ''))
        stages_data = data.get('stages', {})

        for sid, sdata in stages_data.items():
            node = sm.add_stage(sid, sdata.get('config', {}))
            node.state = StageState(sdata['state'])
            node.error = sdata.get('error')
            node.started_at = sdata.get('started_at')
            node.completed_at = sdata.get('completed_at')

        sm.edges = data.get('edges', {})
        sm.current_stage_id = data.get('current_stage_id')
        sm.status = data.get('status', 'resumed')
        return sm

    def list_checkpoints(self, project_id: str) -> list[str]:
        runs = self.workspace.list_runs(project_id)
        checkpoints = []
        for run_id in runs:
            cp = self.workspace.read_artifact(project_id, run_id, 'checkpoint.json')
            if cp:
                checkpoints.append(run_id)
        return checkpoints
