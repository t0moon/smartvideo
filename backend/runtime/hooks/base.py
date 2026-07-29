from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PipelineHook(ABC):
    name: str = 'base_hook'

    @abstractmethod
    async def after_stage(self, project_id: str, stage_id: str, context: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def after_pipeline(self, project_id: str, context: dict[str, Any]) -> None:
        raise NotImplementedError
