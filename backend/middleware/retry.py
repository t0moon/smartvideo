from __future__ import annotations

import asyncio
import random

from middleware.base import AgentMiddleware
from context.schemas import StageContext, StageOutput


class RetryMiddleware(AgentMiddleware):
    name = 'retry'

    def __init__(self, max_retries: int = 3, base_delay: float = 0.5) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def before_stage(self, ctx: StageContext) -> StageContext:
        attempts = ctx.config.get('retry_count', 1)
        ctx.provider_outputs['retry'] = {
            'max_retries': self.max_retries,
            'attempts': attempts,
        }
        return ctx

    async def after_stage(self, ctx: StageContext, output: StageOutput) -> StageOutput:
        if output.error:
            for attempt in range(self.max_retries):
                delay = self.base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                await asyncio.sleep(delay)
                output.error = ''
                ctx.provider_outputs['retry'] = {
                    'retry_attempt': attempt + 1,
                    'delay': delay,
                }
                break
        return output
