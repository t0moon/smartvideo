from __future__ import annotations

from datetime import datetime, timezone

from middleware.base import AgentMiddleware
from context.schemas import StageContext, StageOutput


class AuditMiddleware(AgentMiddleware):
    name = 'audit'

    def __init__(self) -> None:
        self._log: list[dict] = []

    async def before_stage(self, ctx: StageContext) -> StageContext:
        self._log.append({
            'action': 'before_stage',
            'stage_id': ctx.stage_id,
            'project_id': ctx.project_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'inputs': list(ctx.inputs.keys()),
        })
        return ctx

    async def after_stage(self, ctx: StageContext, output: StageOutput) -> StageOutput:
        self._log.append({
            'action': 'after_stage',
            'stage_id': ctx.stage_id,
            'project_id': ctx.project_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'outputs': list(output.outputs.keys()),
            'error': output.error,
        })
        return output

    def get_history(self) -> list[dict]:
        return list(self._log)
