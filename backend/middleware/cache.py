from __future__ import annotations

import hashlib
import json
from typing import Any

from middleware.base import AgentMiddleware
from context.schemas import StageContext, StageOutput


class CacheMiddleware(AgentMiddleware):
    name = 'cache'

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    def _make_key(self, ctx: StageContext) -> str:
        raw = json.dumps({
            'stage_id': ctx.stage_id,
            'project_id': ctx.project_id,
            'inputs': {k: v for k, v in ctx.inputs.items() if v is not None},
        }, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def before_stage(self, ctx: StageContext) -> StageContext:
        key = self._make_key(ctx)
        cached = self._cache.get(key)
        if cached is not None and ctx.stage_id != 'video_gen':
            ctx.provider_outputs['cache'] = {'hit': True, 'key': key}
        else:
            ctx.provider_outputs['cache'] = {'hit': False, 'key': key}
        return ctx

    async def after_stage(self, ctx: StageContext, output: StageOutput) -> StageOutput:
        if not output.error:
            key = self._make_key(ctx)
            self._cache[key] = dict(output.outputs)
        return output
