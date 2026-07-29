from __future__ import annotations

from typing import Any

from context.schemas import StageContext


class ContextManager:
    def __init__(self) -> None:
        self._cache: dict[str, StageContext] = {}

    def get(self, project_id: str, stage_id: str) -> StageContext | None:
        key = f'{project_id}:{stage_id}'
        return self._cache.get(key)

    def set(self, ctx: StageContext) -> None:
        key = f'{ctx.project_id}:{ctx.stage_id}'
        self._cache[key] = ctx

    def invalidate(self, project_id: str, stage_id: str | None = None) -> None:
        if stage_id:
            self._cache.pop(f'{project_id}:{stage_id}', None)
        else:
            keys = [k for k in self._cache if k.startswith(f'{project_id}:')]
            for k in keys:
                self._cache.pop(k, None)

    def clear(self) -> None:
        self._cache.clear()
