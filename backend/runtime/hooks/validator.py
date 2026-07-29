from __future__ import annotations

from typing import Any

from runtime.hooks.base import PipelineHook


class ValidatorHook(PipelineHook):
    name = 'validator'

    async def after_stage(self, project_id: str, stage_id: str, context: dict[str, Any]) -> None:
        output = context.get('output', {})
        expected_keys = context.get('expected_outputs', [])
        missing = [k for k in expected_keys if k not in output]
        if missing:
            context['_validation_errors'] = missing

    async def after_pipeline(self, project_id: str, context: dict[str, Any]) -> None:
        pass
