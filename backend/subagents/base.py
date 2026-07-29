from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseSubagent(ABC):
    name: str = 'base'

    @abstractmethod
    async def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
