from __future__ import annotations

from typing import Any

import yaml

from runtime.state_machine import WorkflowStateMachine, StageNode
from context.builder import ContextBuilder
from middleware.registry import get_registry as get_middleware_registry
from app.config import WORKFLOWS_DIR


class StageExecutor:
    def __init__(self) -> None:
        self.context = ContextBuilder()

    def load_workflow(self, name: str = 'product_ad') -> WorkflowStateMachine:
        path = WORKFLOWS_DIR / f'{name}_v1.yaml'
        if not path.exists():
            path = WORKFLOWS_DIR / f'{name}.yaml'
        if not path.exists():
            raise FileNotFoundError(f'Workflow not found: {name}')

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        sm = WorkflowStateMachine(workflow_name=data.get('name', name))
        stages = data.get('stages', [])

        for stage in stages:
            sid = stage['id']
            sm.add_stage(sid, stage)

        for stage in stages:
            sid = stage['id']
            nxt = stage.get('next')
            sm.add_edge(sid, nxt)

        return sm

    async def execute_stage(self, sm: WorkflowStateMachine, stage_id: str, project_id: str, brief: str = '') -> dict[str, Any]:
        node = sm.start_stage(stage_id)
        if not node:
            return {'error': f'Stage {stage_id} not found'}

        middleware = get_middleware_registry()

        try:
            # Build context and run middleware before
            ctx = self.context.build(project_id, stage_id)
            ctx = await middleware.run_before(ctx)

            # Execute the agent via context builder's run_stage
            output = await self.context.run_stage(project_id, stage_id, brief)

            # Run middleware after
            output = await middleware.run_after(ctx, output)

            if output.error:
                sm.fail_stage(stage_id, output.error)
                return {'error': output.error}

            sm.complete_stage(stage_id, output.outputs)
            return output.outputs

        except Exception as exc:
            error = str(exc)
            sm.fail_stage(stage_id, error)
            return {'error': error}

    async def execute_workflow(self, workflow_name: str, project_id: str, brief: str = '') -> dict[str, Any]:
        sm = self.load_workflow(workflow_name)
        stages = sm.get_ordered_stages()
        outputs: dict[str, Any] = {}

        for stage_id in stages:
            node = sm.get_stage(stage_id)
            if not node:
                continue

            # Skip if stage config says pause_for_review and already paused
            config = node.config
            if config.get('pause_for_review', False):
                from review.service import ReviewService
                svc = ReviewService()
                if svc.is_project_blocked(project_id):
                    sm.pause_stage(stage_id)
                    outputs['_paused'] = True
                    outputs['_pause_stage'] = stage_id
                    break

            result = await self.execute_stage(sm, stage_id, project_id, brief)
            if 'error' in result:
                outputs['_error'] = result['error']
                break

            outputs[stage_id] = result

        outputs['_state'] = sm.to_dict()
        return outputs

    async def resume_workflow(self, project_id: str, resume_from: str) -> dict[str, Any]:
        from project.service import ProjectService
        svc = ProjectService()
        project = svc.get_project(project_id)
        brief = project.brief

        sm = self.load_workflow(project.workflow_name)
        stages = sm.get_ordered_stages()

        resume_index = next((i for i, s in enumerate(stages) if s == resume_from), 0)
        remaining = stages[resume_index:]
        outputs: dict[str, Any] = {}

        for stage_id in remaining:
            result = await self.execute_stage(sm, stage_id, project_id, brief)
            if 'error' in result:
                outputs['_error'] = result['error']
                break
            outputs[stage_id] = result

        outputs['_state'] = sm.to_dict()
        return outputs
