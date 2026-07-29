from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from runtime.hooks.base import PipelineHook
from runtime.checkpoint import CheckpointManager


class PersisterHook(PipelineHook):
    name = 'persister'

    async def after_stage(self, project_id: str, stage_id: str, context: dict[str, Any]) -> None:
        state_machine = context.get('_state_machine')
        if state_machine:
            cp = CheckpointManager()
            cp.save(project_id, state_machine)

    async def after_pipeline(self, project_id: str, context: dict[str, Any]) -> None:
        audit = {
            'action': 'pipeline_completed',
            'project_id': project_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'stages_completed': list(context.keys()),
        }
        from workspace.manager import WorkspaceManager
        mgr = WorkspaceManager()
        mgr.write_artifact(project_id, 'default', 'pipeline_audit.json', audit)
