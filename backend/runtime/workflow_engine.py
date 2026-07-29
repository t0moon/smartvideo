from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from runtime.hooks.registry import get_registry


class YAMLWorkflowEngine:
    def __init__(self, workflows_dir: Path | None = None) -> None:
        from app.config import WORKFLOWS_DIR
        self.workflows_dir = workflows_dir or WORKFLOWS_DIR

    def load_workflow(self, name: str = 'product_ad') -> dict[str, Any]:
        path = self.workflows_dir / f'{name}_v1.yaml'
        if not path.exists():
            path = self.workflows_dir / f'{name}.yaml'
        if not path.exists():
            raise FileNotFoundError(f'Workflow not found: {name}')
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get_stages(self, workflow: dict[str, Any]) -> list[dict[str, Any]]:
        return workflow.get('stages', [])

    def get_hooks(self, workflow: dict[str, Any]) -> dict[str, list[str]]:
        return workflow.get('hooks', {})

    def get_stage(self, workflow: dict[str, Any], stage_id: str) -> dict[str, Any] | None:
        for stage in workflow.get('stages', []):
            if stage.get('id') == stage_id:
                return stage
        return None

    async def execute_pipeline(self, project_id: str, workflow_name: str, context: dict[str, Any]) -> dict[str, Any]:
        workflow = self.load_workflow(workflow_name)
        stages = self.get_stages(workflow)
        registry = get_registry()

        for stage in stages:
            stage_id = stage['id']
            print(f'  [Workflow] Stage: {stage_id}')

            # Run after_stage hooks
            await registry.run_after_stage(project_id, stage_id, context)

            # If stage requires review and is paused, stop here
            if stage.get('pause_for_review', False):
                print(f'  [Workflow] Pausing for review after: {stage_id}')
                context['_paused'] = True
                context['_pause_stage'] = stage_id
                break

        # Run after_pipeline hooks if not paused
        if not context.get('_paused'):
            await registry.run_after_pipeline(project_id, context)

        return context
