from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from context.schemas import StageContext, StageOutput


class AgentMiddleware(ABC):
    name: str = 'base'

    async def before_stage(self, ctx: StageContext) -> StageContext:
        return ctx

    async def after_stage(self, ctx: StageContext, output: StageOutput) -> StageOutput:
        return output
